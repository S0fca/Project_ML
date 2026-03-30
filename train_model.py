import joblib
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.metrics import classification_report, accuracy_score

X_TRAIN_PATH = "data/X_train.csv"
X_TEST_PATH = "data/X_test.csv"
Y_TRAIN_PATH = "data/y_train.csv"
Y_TEST_PATH = "data/y_test.csv"

MODEL_OUTPUT = "news_model.joblib"


def load_y(path: str) -> pd.Series:
    y = pd.read_csv(path)
    if y.shape[1] == 1:
        s = y.iloc[:, 0].astype(str)
        s.name = "category"
        return s
    if "category" in y.columns:
        return y["category"].astype(str)
    s = y.iloc[:, 0].astype(str)
    s.name = "category"
    return s


def main() -> None:
# Nacteni dat
    X_train = pd.read_csv(X_TRAIN_PATH)
    X_test = pd.read_csv(X_TEST_PATH)
    y_train = load_y(Y_TRAIN_PATH)
    y_test = load_y(Y_TEST_PATH)

    X_train = X_train.drop(columns=[c for c in ["images", "comments"] if c in X_train.columns], errors="ignore")
    X_test = X_test.drop(columns=[c for c in ["images", "comments"] if c in X_test.columns], errors="ignore")

    print("X_train:", X_train.shape, "y_train:", y_train.shape)
    print("X_test:", X_test.shape, "y_test:", y_test.shape)

# Rozdeleni sloupcu
    text_cols = [c for c in ["content", "title"] if c in X_train.columns]
    numeric_cols = [c for c in X_train.columns if c not in text_cols]

# Uprava prazdnych hodnot
    if "content" in text_cols:
        X_train["content"] = X_train["content"].fillna("").astype(str)
        X_test["content"] = X_test["content"].fillna("").astype(str)
    if "title" in text_cols:
        X_train["title"] = X_train["title"].fillna("").astype(str)
        X_test["title"] = X_test["title"].fillna("").astype(str)

    for c in numeric_cols:
        X_train[c] = pd.to_numeric(X_train[c], errors="coerce").fillna(0)
        X_test[c] = pd.to_numeric(X_test[c], errors="coerce").fillna(0)



# Vektorizace

    transformers = []

    # text
    if "content" in text_cols:
        transformers.append((
            "tfidf_content",
            TfidfVectorizer(
                max_features=60_000,
                ngram_range=(1, 2),
                min_df=3,
                sublinear_tf=True,
            ),
            "content",
        ))

    # title
    if "title" in text_cols:
        transformers.append((
            "tfidf_title",
            TfidfVectorizer(
                max_features=15_000,
                ngram_range=(1, 2),
                min_df=2,
                sublinear_tf=True,
            ),
            "title",
        ))

# Standardizace numeric_cols
    if numeric_cols:
        transformers.append(("num", StandardScaler(with_mean=False), numeric_cols))

# Aplikace uprav dat na sloupcich
    preprocessor = ColumnTransformer(transformers=transformers, remainder="drop")

# Model
    classifier_model = LinearSVC(class_weight="balanced", max_iter=20000)

# Upravit data, vytvorit model
    pipeline = Pipeline([
        ("preprocess", preprocessor),
        ("classifier", classifier_model),
    ])

    print("\n...")

    pipeline.fit(X_train, y_train)

# Predikce
    y_pred = pipeline.predict(X_test)

# Vysledky
    accuracy = accuracy_score(y_test, y_pred)
    print("Accuracy:", round(accuracy, 4))
    print("\nClassification report:\n")
    print(classification_report(y_test, y_pred, zero_division=0))

    with open("vysledky.txt", "w", encoding="utf-8") as f:
        f.write(f"Accuracy: {round(accuracy, 4)}\n\n")
        f.write("Classification report:\n\n")
        f.write(classification_report(y_test, y_pred, zero_division=0))

# Ulozit model
    joblib.dump(pipeline, MODEL_OUTPUT)
    print(f"\nModel uložen jako {MODEL_OUTPUT}")


if __name__ == "__main__":
    main()