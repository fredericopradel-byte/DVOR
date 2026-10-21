# Historical chart corpus

Eight original DECEA/AISWEB PDFs supplied by the project owner for importer development.
Their filenames and SHA-256 digests are recorded in `manifest.json`. They are historical
samples; neither file dates nor extraction results establish current validity.

Stage 2 assertions compare the **published identification** with the retained PDFs:

| Sample | Expected identification / property |
| --- | --- |
| SBNT ILS Y 16L | ILS title, GNSS requirement, RNAV1/RNP1 note |
| SBNT ILS W / LOC W 16L | Separate ILS/LOC capabilities, DME, textual DME arc |
| SBNT VOR Z 12 | Conventional VOR, textual holding and missed approach |
| SBNT VOR W 16L | VOR, DME and textual DME arc |
| SBNT VOR Y 12 | VOR, DME and textual DME arc |
| SBNT RNP 16L | RNP APCH and branched layout visible in the original |
| SBRJ EVSOB 1D 20L | SID with aid-based definitions and schematics marked NOT TO SCALE |
| SBBQ NDB 18 | Raster-only PDF: no fabricated extraction of NDB identity |

The SBBQ page contains 24 images and no extractable text in the supplied file.
Its visible identification is known to the human reader; the current local extractor
must report missing OCR rather than copying the filename into recognized fields.

The SBRJ PDF encodes many letters individually. Tests verify grouping by published
text placement rather than blindly inserting a space between PDF text items.

These fixtures are **not yet geometry goldens**. They do not validate reconstruction
of arcs, racetracks, transitions, missed approaches, fix positions or vertical paths.
Those expected models must be independently reviewed during stages 3–5. Synthetic
multi-page PDFs and PNG/JPEG fixtures are generated in memory by the test suite.
