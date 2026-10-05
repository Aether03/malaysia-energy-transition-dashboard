# Malaysia state boundaries

`mys_adm1.topojson` is the Shape Map boundary layer for the state-level pages: 16 ADM1 units
(13 states and 3 federal territories) in one object, `MYSADM1gbOpen`. Each geometry carries
`shapeName`, `shapeISO`, `shapeID`, `shapeGroup` and `shapeType`; `dw.dim_state` joins on `shapeISO`
(`iso_3166_2`) and `shapeName` (`geo_shape_name`).

- Source: geoBoundaries gbOpen, MYS ADM1, boundaryID `MYS-ADM1-15666254`
- Pinned URL: https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/MYS/ADM1/geoBoundaries-MYS-ADM1.topojson
- SHA-256: `b358676a9a2f85e2a713670dcda51564e0d492790cec6b3d7fd359c07dbbb0bd` (795,812 bytes)

## Licence

Open Data Commons Open Database Licence (ODbL) 1.0. Required credit:

> Boundaries © OpenStreetMap contributors, via geoBoundaries (ODbL 1.0)

The file is redistributed unmodified under ODbL 1.0 (https://opendatacommons.org/licenses/odbl/1-0/).

## Re-fetch or verify

```
.venv/Scripts/python tools/fetch_map.py            # download, verify hash and content, write
.venv/Scripts/python tools/fetch_map.py --check    # verify the local file only
```
