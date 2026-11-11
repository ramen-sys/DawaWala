# Knowledge-base sources

Record every data source here before using it (SRS 5.3). Check the licence
allows use in this project and note any attribution it requires.

Each curated rule's `source` column names the documents and sections it rests on, for example
`FDA label: Plavix (clopidogrel) §5.1, §7.2`. The exact URL, a supporting quote and the
evidence verdict for every rule are in [review/evidence_check.csv](review/evidence_check.csv).

Rule descriptions are written in our own plain language. No label or guideline text is copied
into the app, so only citation is needed for the reference sources below.

## Datasets

| Source | What it provides | Licence / terms | Accessed |
|---|---|---|---|
| [Pakistan Medicines Dataset For Machine Learning](https://www.kaggle.com/datasets/muhammadabdullah222/pakistan-medicines-dataset) by Muhammad Abdullah, version 3 (2025-09-06). Tag: `Kaggle: Pakistan Medicines Dataset (muhammadabdullah222), version 3` | Brand names, indications, side effects and age restrictions for 69 medications (`pakistan_medicines_dataset.csv`, imported by `scripts.import_medicines`) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Attribution required (see below), including a note that the data was changed. | 2026-11-04 |
| Hand-written list. Tag: `Curated knowledge base (knowledge_base/data/medications.csv)` | Medicines that curated rules need but the Kaggle dataset lacks (e.g. warfarin, metformin) | n/a | 2026-11-04 |

## References for the curated rules (interactions, contraindications, cascades)

| Source | Used for | Terms | Accessed |
|---|---|---|---|
| US FDA prescribing information, read on [DailyMed](https://dailymed.nlm.nih.gov/) (NLM) and [Drugs@FDA](https://www.accessdata.fda.gov/scripts/cder/daf/): Jantoven (warfarin), Plavix (clopidogrel), Zocor (simvastatin), Lipitor (atorvastatin), Aldactone (spironolactone), Zestril (lisinopril), ibuprofen tablets Rx, Naprosyn/naproxen tablets, Reglan (metoclopramide), Aricept (donepezil), Lasix (furosemide), metformin HCl tablets, oxybutynin chloride tablets, Ofirmev (acetaminophen) | Interactions INT-0001 to INT-0015, contraindications CI-0001 to CI-0008 | US government information; free to cite | 2026-11-04 |
| UK Summaries of Product Characteristics on the [electronic medicines compendium](https://www.medicines.org.uk/emc): Simvastatin 20 mg, Paracetamol 500 mg (Zentiva) | CI-0004, CI-0005 | Cited only | 2026-11-04 |
| [EMA press release, 26 July 2013](https://www.ema.europa.eu/en/news/european-medicines-agency-recommends-changes-use-metoclopramide): changes to the use of metoclopramide | CI-0008 | Cited only | 2026-11-04 |
| 2023 American Geriatrics Society Beers Criteria Update Expert Panel. *J Am Geriatr Soc* 2023;71(7):2052-2081. [PMC full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC12478568) | Older-adult and kidney-function risk factors; INT-0007, INT-0011, INT-0013, INT-0015, CI-0002, CI-0003, CI-0006, CI-0007 | Copyrighted guideline; cited only, tables not reproduced | 2026-11-04 |
| McCarthy LM et al. ThinkCascades: a tool for identifying clinically important prescribing cascades affecting older people. *Drugs Aging* 2022. [PMC9477172](https://pmc.ncbi.nlm.nih.gov/articles/PMC9477172) | CAS-0001, CAS-0004 | Cited only | 2026-11-04 |
| Savage RD et al. *JAMA Intern Med* 2020 (calcium channel blockers and loop diuretics). [PMID 32091538](https://pubmed.ncbi.nlm.nih.gov/32091538/) | CAS-0001 | Cited only | 2026-11-04 |
| Gill SS et al. A prescribing cascade involving cholinesterase inhibitors and anticholinergic drugs. *Arch Intern Med* 2005;165(7):808-813. [PMID 15824303](https://pubmed.ncbi.nlm.nih.gov/15824303/) | CAS-0002 | Cited only | 2026-11-04 |
| Avorn J et al. Increased incidence of levodopa therapy following metoclopramide use. *JAMA* 1995;274(22):1780-2. [PMID 7500509](https://pubmed.ncbi.nlm.nih.gov/7500509/) | CAS-0003 | Cited only | 2026-11-04 |
| Gurwitz JH et al. Initiation of antihypertensive treatment during NSAID therapy. *JAMA* 1994;272(10):781-6. [PMID 8078142](https://pubmed.ncbi.nlm.nih.gov/8078142/) | CAS-0004 | Cited only | 2026-11-04 |

All rules must still be approved by a pharmacist or physician before any use beyond the
academic prototype (SAF-09). See [review/README.md](review/README.md).

## Attribution text (CC BY 4.0)

Show this wherever the knowledge base is credited, for example the About page or the report:

> Medication data adapted from "Pakistan Medicines Dataset For Machine Learning" by Muhammad Abdullah (Kaggle, version 3), licensed under CC BY 4.0. Brand names were mapped to generic names and only selected columns are used.
