# extract.py - SQLite Forensic Data Recovery Tool

`extract.py` is a Python script designed for forensic analysis and data recovery from SQLite database files. It can parse SQLite files, recover deleted records that haven't been vacuumed, and extract images embedded within BLOB fields. The tool supports outputting recovered data in both SQLite and CSV formats.

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
  - [Basic Usage](#basic-usage)
  - [Command-Line Arguments](#command-line-arguments)
  - [Examples](#examples)
- [Limitations](#limitations)
- [License](#license)

## Features

- Recover data from SQLite database files, including deleted records not yet vacuumed.
- Parse unallocated pages and the freelist to extract additional data.
- Output recovered data to a new SQLite database or a CSV file.
- Extract images from BLOB fields and save them as separate image files.
- Supports identification of common image formats (JPEG, PNG, GIF, BMP, TIFF, ICO).

## Requirements

- Python 3.x
- Standard Python libraries:
  - `sys`
  - `struct`
  - `sqlite3`
  - `argparse`
  - `csv`
  - `os`

## Installation

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/conorarmstrong/sqlite_extract.git
   ```

2. **Navigate to the Directory:**

   ```bash
   cd sqlite_extract
   ```

3. **Ensure Python 3 is Installed:**

   Verify that Python 3 is installed on your system:

   ```bash
   python3 --version
   ```

## Usage

### Basic Usage

```bash
python3 extract.py -i INPUT_FILE -o OUTPUT_FILE [options]
```

### Command-Line Arguments

- `-i`, `--input` (required): Path to the input SQLite database file.
- `-o`, `--output` (required): Path for the output file (SQLite database or CSV file).
- `-f`, `--format`: Output format. Choose between `sqlite` (default) or `csv`.
- `-e`, `--extract-images`: Flag to enable extraction of images from BLOB fields.
- `-d`, `--image-dir`: Directory to save extracted images (default is `images`).

### Examples

#### Recover Data to a New SQLite Database

```bash
python3 extract.py -i corrupted.db -o recovered.db
```

#### Recover Data to a CSV File

```bash
python3 extract.py -i corrupted.db -o recovered_data.csv -f csv
```

#### Recover Data and Extract Images to Default Directory

```bash
python3 extract.py -i corrupted.db -o recovered.db -e
```

#### Recover Data, Extract Images, and Specify Image Directory

```bash
python3 extract.py -i corrupted.db -o recovered_data.csv -f csv -e -d extracted_images
```

#### Full Help Message

For a complete list of options:

```bash
python3 extract.py -h
```

### Output Explanation

- **SQLite Output (`-f sqlite`):**
  - Creates a new SQLite database containing a table named `recovered_data`.
  - Columns are named `field1`, `field2`, ..., based on the maximum number of fields in the recovered records.
  - If image extraction is enabled, BLOB fields containing images are replaced with the filenames of the extracted images.

- **CSV Output (`-f csv`):**
  - Generates a CSV file with a header row (`field1`, `field2`, ...).
  - BLOB fields are converted to hexadecimal strings unless they contain images and image extraction is enabled.
  - Extracted images are saved in the specified image directory.

## Limitations

- **Schema Reconstruction:**
  - Without access to the original `sqlite_master` table, the script cannot reconstruct the exact table schemas.
  - All recovered data is stored in a generic table with columns named `field1`, `field2`, etc.

- **Data Integrity:**
  - Recovered data may be incomplete or corrupted, especially if the database file is heavily damaged.
  - Validate critical data before relying on it.

- **Image Extraction:**
  - The script identifies images based on common file signatures (magic numbers).
  - Images in unsupported formats or with non-standard signatures may not be extracted.

- **Unsupported Features:**
  - The script does not handle indexes, triggers, views, or other SQLite-specific constructs beyond basic tables.

## License

This project is licensed under the [MIT License](LICENSE).

---

**Disclaimer:**

- **Legal and Ethical Use:**
  - Ensure you have the legal right to recover and access the data in the database file.
  - Use the recovered data responsibly, respecting privacy and confidentiality.

- **Data Handling:**
  - Always work on a copy of the database file to prevent accidental modifications.
  - Handle sensitive data securely and in compliance with applicable laws and regulations.

---

**Contributions and Feedback:**

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/yourusername/yourrepository/issues) if you have any questions or suggestions.

---

**Contact Information:**

- **Author:** Conor Armstrong
- **Email:** conorarmstrong@gmail.com
- **GitHub:** [conorarmstrong](https://github.com/conorarmstrong)

---

