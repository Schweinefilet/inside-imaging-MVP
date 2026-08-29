"""Generate the synthetic DICOM fixture used by the test suite.

Run from the project root:
    python scripts/make_sample_dcm.py

Writes tests/fixtures/sample.dcm.
"""

import datetime
from pathlib import Path

import numpy as np
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import generate_uid, UID, ExplicitVRLittleEndian

OUT_PATH = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "sample.dcm"

ds = FileDataset(str(OUT_PATH), {}, is_implicit_VR=False, is_little_endian=True)

# Required DICOM meta
ds.file_meta = FileMetaDataset()
ds.file_meta.MediaStorageSOPClassUID    = UID('1.2.840.10008.5.1.4.1.1.2')  # CT Image Storage
ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
ds.file_meta.TransferSyntaxUID          = ExplicitVRLittleEndian

# Patient / study identifiers
ds.PatientName          = 'Test^Patient'
ds.PatientID            = 'TEST001'
ds.StudyInstanceUID     = generate_uid()
ds.SeriesInstanceUID    = generate_uid()
ds.SOPInstanceUID       = ds.file_meta.MediaStorageSOPInstanceUID
ds.SOPClassUID          = ds.file_meta.MediaStorageSOPClassUID
ds.Modality             = 'CT'
ds.StudyDescription     = 'Sample CT Study'
ds.AccessionNumber      = 'ACC12345'
ds.StudyDate            = datetime.date.today().strftime('%Y%m%d')
ds.StudyTime            = '120000'

# Image data — 512×512 grayscale
ds.Rows                 = 512
ds.Columns              = 512
ds.BitsAllocated        = 16
ds.BitsStored           = 16
ds.HighBit              = 15
ds.PixelRepresentation  = 1
ds.SamplesPerPixel      = 1
ds.PhotometricInterpretation = 'MONOCHROME2'
ds.PixelData            = np.zeros((512, 512), dtype=np.int16).tobytes()

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
pydicom.dcmwrite(str(OUT_PATH), ds, write_like_original=False)
print(f'Wrote {OUT_PATH}')
