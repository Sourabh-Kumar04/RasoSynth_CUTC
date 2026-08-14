# Open Data Repositories — Comprehensive Reference

This document catalogs open data repositories actively used by the RasoDataset-Agent
discovery pipeline.  Sources are organized by type with API access details.

## Primary ML Dataset Repositories

| Repository | URL | API | Auth | Notes |
|---|---|---|---|---|
| **HuggingFace Datasets** | <https://huggingface.co/datasets> | `GET /api/datasets?search=&sort=&direction=` | None (read) | Largest collection; 100k+ datasets with downloading SDK |
| **Kaggle** | <https://kaggle.com/datasets> | `GET /api/i/documentation.DatasetsService/DatasetsList` | API key (free) | 300k+ datasets; competitions API |
| **OpenML** | <https://openml.org> | `GET /api/v1/json/data/list/` | None (read) | Curated ML datasets with task definitions & benchmarking |
| **Papers with Code** | <https://paperswithcode.com/datasets> | `GET /api/v1/datasets/?q=` | None | Maps papers→datasets→code→results |
| **UCI ML Repository** | <https://archive.ics.uci.edu> | `GET /api/datasets?search=` | None | Classic benchmark repository; 600+ datasets |
| **TensorFlow Datasets** | <https://tensorflow.org/datasets> | Python SDK (`tensorflow_datasets`) | None | Google-curated, versioned; 300+ datasets |
| **TorchVision Datasets** | <https://pytorch.org/vision> | Python SDK (`torchvision.datasets`) | None | PyTorch ecosystem datasets |

## Government & Institutional Open Data

| Repository | URL | API | Auth | Notes |
|---|---|---|---|---|
| **Data.gov (US)** | <https://data.gov> | `GET /api/3/action/package_search?q=` (CKAN) | None | 300k+ US government datasets |
| **Data.gov.uk (UK)** | <https://data.gov.uk> | CKAN API | None | UK public sector datasets |
| **Data.europa.eu (EU)** | <https://data.europa.eu> | `GET /api/hub/search/search?q=` | None | Aggregates all EU open data portals |
| **Data.gouv.fr (France)** | <https://data.gouv.fr> | CKAN API | None | French public datasets |
| **Open Canada** | <https://open.canada.ca> | CKAN API | None | Canadian government data |
| **Data.gov.au (Australia)** | <https://data.gov.au> | CKAN API | None | Australian government data |
| **Open Data Swiss** | <https://opendata.swiss> | CKAN API | None | Swiss government data |
| **Berlin Open Data** | <https://daten.berlin.de> | CKAN API | None | Berlin city data |
| **Eurostat** | <https://ec.europa.eu/eurostat> | REST API + bulk downloads | None | European statistics |

## Academic & Research Repositories

| Repository | URL | API | Auth | Notes |
|---|---|---|---|---|
| **Zenodo** | <https://zenodo.org> | `GET /api/records?q=&type=dataset` | None | CERN-hosted; DOIs for all records |
| **Figshare** | <https://figshare.com> | `POST /api/v2/articles/search` | None (for public) | Research outputs incl. datasets |
| **Harvard Dataverse** | <https://dataverse.harvard.edu> | `GET /api/search?q=&type=dataset` | None | Social science focus; 100k+ datasets |
| **Dryad** | <https://datadryad.org> | REST API | None | Scientific & medical data |
| **DataONE** | <https://dataone.org> | REST API | None | Earth/environmental science data federation |
| **ICPSR** | <https://icpsr.umich.edu> | REST API | Account required | Social science data archive |
| **UK Data Service** | <https://ukdataservice.ac.uk> | REST API | Account required | UK social & economic data |

## Domain-Specific Data Repositories

| Repository | URL | Domain | API | Notes |
|---|---|---|---|---|
| **Stanford SNAP** | <https://snap.stanford.edu/data> | Network/Graph | Scrape listing page | 50+ large-scale network datasets |
| **AWS Open Data Registry** | <https://registry.opendata.aws> | Multi-domain | `GET /api/v1/datasets?search=` | Datasets hosted on AWS (free egress) |
| **NASA Earth Data** | <https://earthdata.nasa.gov> | Earth Science | CMR API | Satellite imagery, climate, terrain |
| **NOAA Data** | <https://noaa.gov/data> | Weather/Climate | REST API | Historical weather, ocean, climate |
| **NCBI / PubMed** | <https://ncbi.nlm.nih.gov> | Biomedical | E-utilities API | Genomic, protein, literature |
| **World Bank Data** | <https://data.worldbank.org> | Economics | `GET /api/v2/indicator?search=` | Global development indicators |
| **IMF Data** | <https://imf.org/en/Data> | Economic/Financial | REST API | Macroeconomic & financial data |
| **UN Data** | <https://data.un.org> | Multi-domain | REST API | UN statistics database |
| **WHO Data** | <https://who.int/data> | Health | REST API | Global health statistics |
| **Common Crawl** | <https://commoncrawl.org> | Web/Text | S3 + columnar indexes | Petabyte-scale web crawl archives |
| **OPUS** | <https://opus.nlpl.eu> | NLP/Translation | Download | 700+ parallel corpora (aligned text) |
| **Open Images** | <https://storage.googleapis.com/openimages> | Computer Vision | Download | 9M annotated images |
| **Common Voice** | <https://commonvoice.mozilla.org> | Speech/Audio | Download | 30k+ hours of speech in 100+ languages |
| **Roboflow** | <https://roboflow.com> | Computer Vision | REST API (API key) | 200k+ CV datasets with annotations |
| **MoleculeNet** | <https://moleculenet.org> | Chemistry/ML | Download | Molecular ML benchmark datasets |
| **Protein Data Bank** | <https://rcsb.org> | Structural Biology | REST API | 200k+ 3D protein structures |
| **ImageNet** | <https://image-net.org> | Computer Vision | Download (account) | 14M+ labeled images |

## Aggregator Portals

| Portal | URL | Notes |
|---|---|---|
| **Google Dataset Search** | <https://datasetsearch.research.google.com> | Meta-search across all schema.org-annotated datasets |
| **DataPortals.org** | <https://dataportals.org> | Aggregates 600+ open data portals globally |
| **DataHub.io** | <https://datahub.io> | Community data management (CKAN-based) |
| **Registry of Research Data Repositories (re3data)** | <https://re3data.org> | Registers 3k+ research data repositories |
| **Awesome Public Datasets (GitHub)** | <https://github.com/awesomedata/awesome-public-datasets> | Curated list of free/public datasets |
| **Wikipedia: List of ML Datasets** | <https://en.wikipedia.org/wiki/List_of_datasets_for_machine-learning_research> | Comprehensive wiki list |

## Additional Notable Sources

| Repository | URL | Domain | Notes |
|---|---|---|---|
| **Quandl / Nasdaq Data Link** | <https://data.nasdaq.com> | Financial | 20M+ financial/economic time series |
| **OpenStreetMap** | <https://openstreetmap.org> | Geospatial | Complete world map data |
| **GDELT Project** | <https://gdeltproject.org> | News/Events | Global news event database |
| **OpenCitations** | <https://opencitations.net> | Academic | Open bibliographic citation data |
| **Wikidata** | <https://wikidata.org> | General Knowledge | Linked open data, SPARQL queryable |
| **DBpedia** | <https://dbpedia.org> | General Knowledge | Structured Wikipedia data |
| **Yelp Open Dataset** | <https://yelp.com/dataset> | Business/Reviews | 8.6M reviews, 200k businesses |
| **Stack Exchange Data Dump** | <https://archive.org/details/stackexchange> | Q&A | All Stack Exchange Q&A data |
| **MovieLens** | <https://grouplens.org/datasets/movielens/> | Recommendation | Classic recommendation systems data |
| **CIFAR / MNIST** | Various | CV benchmarks | Standard image classification benchmarks |
| **GLUE / SuperGLUE** | <https://gluebenchmark.com> | NLP benchmarks | NLP benchmark leaderboards |
| **MMLU** | <https://github.com/hendrycks/test> | LLM evaluation | Massive Multitask Language Understanding |
| **The Pile** | <https://pile.eleuther.ai> | Language Modeling | 825 GB diverse text corpus |
| **LAION** | <https://laion.ai> | Vision-Language | 5B image-text pairs |

## Discovery Strategy

The pipeline uses a **three-tier approach** for each source:

1. **Native API** — Direct REST/JSON APIs (OpenML, Zenodo, HuggingFace, Kaggle, Figshare, etc.)
2. **Web scraping** — Structured page parsing (Stanford SNAP, UCI)
3. **Web search fallback** — DuckDuckGo/Google/Brave search scoped to the repository domain (site:example.com)

Sources are prioritized as follows:
- **Tier 1** (always searched): HuggingFace, Kaggle, OpenML, Zenodo, Papers with Code, AWS Open Data, Figshare
- **Tier 2** (searched by default): Government data portals, DataHub.io, UCI, SNAP, DataPortals.org
- **Tier 3** (on-demand): GitHub repos, ArXiv, Wikipedia, StackOverflow, HackerNews, PDFs

## Adding a New Repository

To add a new data repository to the discovery pipeline:

1. Add a new `SourceType` value in `pipeline/discovery.py`
2. Add the repository URL to `DATASET_PORTALS` class variable
3. Create a `_discover_<name>()` method with:
   - Native API call (preferred)
   - Web scrape fallback
   - DuckDuckGo fallback
4. Wire the method in `_discover_source_type()` dispatch
5. Optionally add to default `source_types` in `discover()`
6. Add to SEARCH_QUERIES for secondary discovery