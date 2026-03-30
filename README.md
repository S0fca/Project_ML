# Predicke kategorií článků
Aplikace pro sdílení článků a model pro klasifikaci do kategorií

## Přehled
* Model přiřazuje kategorii článku na základě: 
  * textu (content, title) 
  * jednoduchých číselných údajů (např.: čas publikace)  

* Součástí projektu je i aplikace pro publikování článků, kde lze při vytváření příspěvku nechat kategorii automaticky navrhnout pomocí tohoto modelu.

## Jak model funguje
### Textová data
* jsou převedena na numerickou reprezentaci pomocí TF-IDF
* používají se:
  * slova (unigramy)
  * dvojice slov (bigramy)
### Numerická data
* jsou standardizována pomocí StandardScaler
### Model
* Linear SVM (LinearSVC)
* parametr class_weight="balanced" řeší nevyváženost tříd
### Pipeline
* preprocessing + model jsou spojeny do jednoho pipeline

## Použité sloupce
* content - text článku
* title - nadpis článku
* hour, weekday, month - data publikace

## Aplikace pro publikování článků
* Jednoduchá webová aplikace (Flask + SQLite)
  * Vytvářet nové články (title, content, published_at)
  * Automaticky navrhovat kategorii článku pomocí natrénovaného modelu
  * Upravit kategorii, pokud je potřeba změnit finální zařazení
  * Prohlížet seznam článků s filtrováním a řazením (nejnovější / nejstarší)
  * Ukládat články do lokální databáze SQLite (posts.db)

### Endpointy API
* GET /api/categories - seznam všech kategorií modelu
* POST /api/predict - predikce kategorie pro daný článek
* POST /api/posts - vytvoření nového článku
* GET /api/posts - seznam uložených článků
* GET /api/posts/<id> - detail konkrétního článku
* PATCH /api/posts/<id> - aktualizace článku (např. finální kategorie)

## Dataset (příklad rozložení kategorií)
| Kategorie           | Počet článků |
|-------------------|-------------|
| hokej             | 1748        |
| zpravy            | 998         |
| sport             | 845         |
| fotbal            | 759         |
| cestovani         | 560         |
| pardubice         | 475         |
| oh                | 297         |
| finance           | 295         |
| ekonomika         | 284         |
| onadnes           | 257         |
| kultura           | 247         |
| praha             | 139         |
| ostrava           | 119         |
| brno              | 105         |
| jihlava           | 102         |
| bydleni           | 100         |
| zlin              | 99          |
| liberec           | 91          |
| plzen             | 90          |
| olomouc           | 87          |
| hradec-kralove    | 87          |
| magaziny          | 83          |
| ceske-budejovice  | 83          |
| usti              | 81          |
| karlovy-vary      | 78          |
| spotrebitel       | 65          |
| volby             | 63          |
| technet           | 55          |
| auto              | 53          |
| xman              | 47          |
| hobby             | 46          |
| jenprozeny        | 23          |
| mobil             | 22          |
| jenproholky       | 13          | 

## Příklad přesnosti modelu
Accuracy: 0.8294

Classification report:

| Kategorie           | Precision | Recall | F1-score | Support |
|-------------------|----------|--------|----------|---------|
| auto              | 1.00     | 1.00   | 1.00     | 1       |
| brno              | 0.25     | 0.50   | 0.33     | 2       |
| bydleni           | 1.00     | 1.00   | 1.00     | 2       |
| ceske-budejovice  | 1.00     | 0.50   | 0.67     | 2       |
| cestovani         | 0.85     | 1.00   | 0.92     | 11      |
| ekonomika         | 0.67     | 0.67   | 0.67     | 6       |
| finance           | 0.80     | 0.67   | 0.73     | 6       |
| fotbal            | 1.00     | 0.87   | 0.93     | 15      |
| hobby             | 1.00     | 1.00   | 1.00     | 1       |
| hokej             | 0.97     | 1.00   | 0.99     | 35      |
| hradec-kralove    | 1.00     | 0.50   | 0.67     | 2       |
| jihlava           | 1.00     | 0.50   | 0.67     | 2       |
| karlovy-vary      | 1.00     | 0.50   | 0.67     | 2       |
| kultura           | 0.67     | 0.80   | 0.73     | 5       |
| liberec           | 0.50     | 0.50   | 0.50     | 2       |
| magaziny          | 0.00     | 0.00   | 0.00     | 2       |
| oh                | 0.86     | 1.00   | 0.92     | 6       |
| olomouc           | 0.00     | 0.00   | 0.00     | 2       |
| onadnes           | 1.00     | 1.00   | 1.00     | 5       |
| ostrava           | 1.00     | 0.50   | 0.67     | 2       |
| pardubice         | 0.56     | 1.00   | 0.72     | 9       |
| plzen             | 1.00     | 0.50   | 0.67     | 2       |
| praha             | 0.67     | 0.67   | 0.67     | 3       |
| sport             | 1.00     | 0.94   | 0.97     | 17      |
| spotrebitel       | 1.00     | 1.00   | 1.00     | 1       |
| technet           | 1.00     | 1.00   | 1.00     | 1       |
| usti              | 0.00     | 0.00   | 0.00     | 2       |
| volby             | 0.00     | 0.00   | 0.00     | 1       |
| xman              | 0.00     | 0.00   | 0.00     | 1       |
| zlin              | 1.00     | 0.50   | 0.67     | 2       |
| zpravy            | 0.71     | 0.85   | 0.77     | 20      |
| **accuracy**      |          |        | 0.83     | 170     |
| **macro avg**     | 0.73     | 0.64   | 0.66     | 170     |
| **weighted avg**  | 0.83     | 0.83   | 0.81     | 170     |

> Hodnoty jsou orientační a slouží pro ilustraci využití modelu. Dataset není součástí repozitáře.

### Frontend
* Formulář pro vložení nového článku
* Tlačítko „Navrhnout“ pro zobrazení predikované kategorie
* Tlačítko „Uložit“ pro uložení článku do databáze
* Seznam článků s možností výběru a zobrazení detailu
