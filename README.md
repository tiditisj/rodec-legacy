# Rodec Legacy

**legacy.rodec.com**: the archive of Rodec, the Belgian brand that has been serving DJs since 1954.

The site covers:

- **History**: from ROger DE Clercq's radio shop in Antwerp to the last Rodec in 2014, with a year-by-year timeline.
- **Models**: every Rodec in the original product register, 86 units from the 1961 Stereofan to the 2010 Patch Live. Each model has photos, the original brochure, its launch price, key features and downloads.
- **Archive**: the 50-years book *Perpetual Music Makers* (2004), the 2010 catalogue, brochures from 1961 onwards, adverts and magazine reviews.
- **Manuals & schematics**: user manuals, service manuals and schematics as free PDFs.
- **DJs & clubs**: photos of DJs and clubs using Rodec, and news from the archive.
- **Useful sources**: where to find spare parts and help with servicing classic units.

Built with [Astro](https://astro.build) as a fully static site and hosted on GitHub Pages.

---

## Getting started

Requires Node 22+.

```bash
npm install
npm run dev        # http://localhost:4321
npm run build      # static site in dist/
```

## Project layout

```
src/
  pages/              one file per page (index, history, models/[slug], archive, manuals, djs, resources)
  layouts/Base.astro  header, footer, menu, image viewer
  components/         model card, document card, gallery, logo
  data/
    content.ts        all hand-written text: timeline, model stories, key features, news
    site.ts           menu and external links
    generated/        models.json, docs.json, archive.json  (written by the asset script)
  styles/global.css   design tokens and shared styles
public/
  media/              optimised photos and scans (webp)
  docs/               PDF manuals, schematics, book and catalogue
  brand/              Rodec logo (vector)
scripts/
  build_assets.py     turns the raw archive into public/ + src/data/generated/
```

### Editing content

| What | Where |
|---|---|
| Story of a model, timeline, key features, news | `src/data/content.ts` |
| Menu items and external links | `src/data/site.ts` |
| Which manual belongs to which model, document titles | `DOC_LIST` in `scripts/build_assets.py` |
| Extra models not in the product register | `EXTRA_MODELS` in `scripts/build_assets.py` |
| Photos taken from the 2010 catalogue | `CATALOGUE_IMAGES` in `scripts/build_assets.py` |

## Rebuilding assets from the archive

The raw archive (photos, scans, manuals and the `RODEC Toestellen history.xls` product register) lives on Google Drive and is **not** in this repository. Only the optimised output in `public/` and `src/data/generated/` is committed.

```bash
python3 -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt   # once
.venv/bin/python scripts/build_assets.py           # incremental: only changed files
.venv/bin/python scripts/build_assets.py --force   # rebuild everything
```

Default source locations (override with environment variables):

| Variable | Default |
|---|---|
| `RODEC_ARCHIVE` | `~/Library/CloudStorage/GoogleDrive-…/My Drive/TDR/Rodec/DAM/Product/ZZ_Legacy` |
| `RODEC_CATALOGUE` | `<DAM>/Marketing/history/rodec_history.pdf` |

The script needs poppler (`pdftoppm`, `pdfimages`) and libtiff (`tiff2rgba`): `brew install poppler libtiff`.

What the script does:
- reads the product register and assigns every model an era, category and series;
- matches photos and brochure scans to models by file name;
- resizes everything to webp at 1800 px plus 640 px thumbnails;
- merges multi-file scans into single PDFs and builds a PDF of the 50-years book;
- pulls product shots and history collages out of the 2010 catalogue;
- removes near-duplicate photos and repairs the few broken old-JPEG TIFFs in the archive.

Deliberately **not** published: dealer and customer lists, price lists, the serial-number archive, and distributor contact persons.

## Deployment

Every push to `main` builds and publishes the site through `.github/workflows/deploy.yml`.

One-time setup:
1. Repository → Settings → Pages → Source: **GitHub Actions**.
2. DNS: a `CNAME` record for `legacy.rodec.com` pointing to `<github-user>.github.io`. The domain is already in `public/CNAME`.
3. Once the certificate has been issued, enable **Enforce HTTPS** in the Pages settings.
