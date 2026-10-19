# models

The program keeps its two offline models here:

- `isnet-general-use.onnx` (about 180 MB)
- `BiRefNet-general-bb_swin_v1_tiny-epoch_232.onnx` (about 225 MB)

They are downloaded the first time the program meets a photo with a busy background,
or when you run:

```
python3 photo_background.py --download-model
```

After that it works without internet. Each download is checked against a checksum, so
a broken download is never used. The files aren't stored on GitHub because they are
bigger than GitHub's 100 MB limit for normal files.
