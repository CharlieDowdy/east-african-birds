# Photo pipeline now implemented

The app now queries iNaturalist at runtime using:
- `photo_license=cc0,cc-by,cc-by-sa`
- `quality_grade=research`

For every photo displayed, the UI keeps the attribution and licence returned by iNaturalist.

Why these licences?
- CC0: no rights reserved.
- CC BY: reuse with attribution.
- CC BY-SA: reuse with attribution and share-alike requirements.

The app deliberately excludes CC BY-NC because a future commercial app would not automatically have permission to use non-commercial media. iNaturalist says licences are attached to individual media and that users retain ownership.

The remaining AI requirement is a trained model. The UI does not claim a prediction until such a model is supplied.
