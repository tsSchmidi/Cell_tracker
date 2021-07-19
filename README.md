# Cell_tracker
Track and analyse rotating cells

Input folder needs to contain a CSV file and a subfolder that contains the image series. Multiple CSV files and subfolders can be handled simultaneously.

CSV files:
Name is assumed to be "Results_<subfolder name>".
Columns are assumed to be labeled "" (index), "Area" (of cell), "Mean", "Min", "Max" (intensity), "X", "Y" (position), "Major" (length), "Minor" (width), "Angle", "Slice" (image #).
These can be generated with ImageJ.

Image series:
Name assumed to be "<series name>-<image #>".
Numbers in all names are used to sort the data.
Filetype assumed to be ".tif".
Image timestamp must be readable by exifread.

The script groups cells across time points as individual cells to analyse their rotation around a point of attachment.
