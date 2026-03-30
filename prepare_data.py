import json
import pandas as pd
from sklearn.model_selection import train_test_split

INPUT_FILE = "data/data.jsonl"
MIN_TEXT_LEN = 500
MAX_TEXT_LEN = 20000

TEST_SIZE = 0.02
RANDOM_STATE = 42
MIN_PER_CLASS = 2


def read_jsonl(path: str) -> pd.DataFrame:
    records = []
    bad = 0
    total = 0
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                records.append(json.loads(line))
            except Exception:
                bad += 1
                continue
    df = pd.DataFrame.from_records(records)
    print(f"Načteno záznamů: {len(df)} | Vadných řádků přeskočeno: {bad} | Celkem řádků: {total}")
    return df


def main() -> None:
# Nacteni dat
    data = read_jsonl(INPUT_FILE)
    print("Původní počet záznamů:", len(data))
    if data.empty:
        raise SystemExit("Dataset je prázdný.")

# Odstranit zaznamy bez: "content", "category", "date"
    required = [c for c in ["content", "category", "date"] if c in data.columns]
    data = data.dropna(subset=required)

# Vyplnit prazdny text
    data["content"] = data["content"].astype(str).fillna("")
    if "title" in data.columns:
        data["title"] = data["title"].astype(str).fillna("")

# Smazat kratke a dlouhe clanky
    data["text_length"] = data["content"].str.len()
    data = data[(data["text_length"] >= MIN_TEXT_LEN) & (data["text_length"] <= MAX_TEXT_LEN)]

# datum
    data["date"] = pd.to_datetime(data["date"], errors="coerce", utc=True)
    data = data.dropna(subset=["date"])

    data["hour"] = data["date"].dt.hour.astype(int)
    data["weekday"] = data["date"].dt.weekday.astype(int)
    data["month"] = data["date"].dt.month.astype(int)

# y
    y = data["category"].astype(str)
    y.name = "category"

# filtr malých tříd
    class_counts = y.value_counts()
    valid = class_counts[class_counts >= MIN_PER_CLASS].index
    removed = len(class_counts) - len(valid)
    if removed > 0:
        print(f"Removed: {removed}, Min: {MIN_PER_CLASS}")
        data = data[data["category"].astype(str).isin(valid)]
        y = data["category"].astype(str)
        y.name = "category"

    print("Delka po cisteni:", len(data))
    print("Pocet trid:", y.nunique())
    print("Kategorie: ")
    print(y.value_counts())

    with open("priprava_dat.txt", "w", encoding="utf-8") as f:
        f.write(f"Kategorie: {y.value_counts()}\n\n")

    drop_cols = {"category", "url", "scraped_at", "images", "comments"}
    drop_cols = [c for c in drop_cols if c in data.columns]
    X = data.drop(columns=drop_cols)

    dt_cols = [c for c in X.columns if pd.api.types.is_datetime64_any_dtype(X[c])]
    if dt_cols:
        X = X.drop(columns=dt_cols)


    keep_object = {"content", "title"}
    obj_drop = [c for c in X.columns if X[c].dtype == "object" and c not in keep_object]
    if obj_drop:
        X = X.drop(columns=obj_drop)

# Uprava prazdnych hodnot
    if "content" in X.columns:
        X["content"] = X["content"].fillna("").astype(str)
    if "title" in X.columns:
        X["title"] = X["title"].fillna("").astype(str)

    for c in X.columns:
        if c in ("content", "title"):
            continue
        X[c] = pd.to_numeric(X[c], errors="coerce").fillna(0)


    print(data.columns.tolist())

# hledani min test size
    n_classes = y.nunique()
    n_samples = len(y)
    min_test_frac = n_classes / n_samples

# Test size
    test_size = TEST_SIZE
    if isinstance(test_size, float) and test_size < min_test_frac:
        test_size = min(min_test_frac + (1 / n_samples), 0.5)
        print(f"TEST_SIZE={test_size:.4f}")

# Split dat
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=RANDOM_STATE,
        stratify=y
    )

    print("\nDone:")
    print("X_train:", X_train.shape, "y_train:", y_train.shape)
    print("X_test:", X_test.shape, "y_test:", y_test.shape)

# Ulozeni dat
    from pathlib import Path

    out_dir = Path("data")
    out_dir.mkdir(parents=True, exist_ok=True)

    X_train.to_csv(out_dir / "X_train.csv", index=False)
    X_test.to_csv(out_dir / "X_test.csv", index=False)
    y_train.to_csv(out_dir / "y_train.csv", index=False, header=True)
    y_test.to_csv(out_dir / "y_test.csv", index=False, header=True)

    print("\nSaved: data/X_train.csv, data/X_test.csv, data/y_train.csv, data/y_test.csv")

if __name__ == "__main__":
    main()