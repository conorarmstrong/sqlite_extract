import sys
import struct
import sqlite3
import argparse
import csv
import os

def read_varint(data, offset):
    """Reads a varint from data starting at offset."""
    value = 0
    for i in range(9):
        if offset + i >= len(data):
            raise IndexError("Offset out of bounds while reading varint.")
        byte = data[offset + i]
        if byte < 0x80:
            value = (value << 7) | byte
            return value, i + 1
        else:
            value = (value << 7) | (byte & 0x7F)
    return value, 9

def parse_serial_type(data, offset, serial_type):
    """Parses a value from data starting at offset based on the serial type."""
    if serial_type >= 12 and serial_type % 2 == 0:
        # Blob
        length = (serial_type - 12) // 2
        value = data[offset:offset+length]
        return value, length
    elif serial_type >= 13 and serial_type % 2 == 1:
        # Text
        length = (serial_type - 13) // 2
        value = data[offset:offset+length].decode('utf-8', errors='replace')
        return value, length
    elif serial_type == 0:
        return None, 0
    elif serial_type == 1:
        value = struct.unpack('>b', data[offset:offset+1])[0]
        return value, 1
    elif serial_type == 2:
        value = struct.unpack('>h', data[offset:offset+2])[0]
        return value, 2
    elif serial_type == 3:
        value = int.from_bytes(data[offset:offset+3], 'big', signed=True)
        return value, 3
    elif serial_type == 4:
        value = struct.unpack('>i', data[offset:offset+4])[0]
        return value, 4
    elif serial_type == 5:
        value = int.from_bytes(data[offset:offset+6], 'big', signed=True)
        return value, 6
    elif serial_type == 6:
        value = struct.unpack('>q', data[offset:offset+8])[0]
        return value, 8
    elif serial_type == 7:
        value = struct.unpack('>d', data[offset:offset+8])[0]
        return value, 8
    elif serial_type == 8:
        return 0, 0
    elif serial_type == 9:
        return 1, 0
    else:
        return None, 0  # For serial types 10 and 11

def parse_record(data, offset, payload_length):
    """Parses a record from data starting at offset with given payload_length."""
    try:
        header_offset = offset
        header_length, n = read_varint(data, header_offset)
        header_offset += n
        if header_length > payload_length:
            return None
        serial_types = []
        bytes_read = n
        while bytes_read < header_length:
            serial_type, n = read_varint(data, header_offset)
            serial_types.append(serial_type)
            header_offset += n
            bytes_read += n
        values = []
        value_offset = offset + header_length
        for serial_type in serial_types:
            value, length = parse_serial_type(data, value_offset, serial_type)
            values.append(value)
            value_offset += length
        return values
    except Exception:
        return None

def parse_page(data, page_number, page_size, records):
    """Parses a page and appends records to the records list."""
    page_offset = page_number * page_size
    page_data = data[page_offset:page_offset+page_size]
    if len(page_data) == 0:
        return
    page_type = page_data[0]
    if page_type not in [0x0D, 0x05]:
        return
    num_cells = struct.unpack('>H', page_data[3:5])[0]
    cell_pointers = []
    header_size = 8 if page_type == 0x0D else 12
    for i in range(num_cells):
        ptr_offset = header_size + i*2
        if ptr_offset + 2 > len(page_data):
            continue
        ptr = struct.unpack('>H', page_data[ptr_offset:ptr_offset + 2])[0]
        cell_pointers.append(ptr)
    for cell_pointer in cell_pointers:
        cell_offset = cell_pointer
        try:
            payload_length, n = read_varint(page_data, cell_offset)
            cell_offset += n
            if page_type == 0x05:
                left_child_page, n = read_varint(page_data, cell_offset)
                cell_offset += n
            rowid, n = read_varint(page_data, cell_offset)
            cell_offset += n
            payload = page_data[cell_offset:cell_offset+payload_length]
            record = parse_record(payload, 0, payload_length)
            if record:
                records.append(record)
        except Exception:
            continue  # Skip malformed cells

def get_freelist_pages(data, page_size, freelist_trunk_page, total_freelist_pages):
    """Traverses the freelist and collects all freelist pages."""
    freelist_pages = []
    pages_collected = 0
    next_trunk_page = freelist_trunk_page
    try:
        while next_trunk_page != 0 and pages_collected < total_freelist_pages:
            page_offset = (next_trunk_page - 1) * page_size
            if page_offset + page_size > len(data):
                print(f"Page offset {page_offset} out of bounds.")
                break
            page_data = data[page_offset:page_offset+page_size]
            freelist_pages.append(next_trunk_page - 1)
            # Ensure there is enough data to unpack
            if len(page_data) < 8:
                print(f"Insufficient data to read freelist trunk page at page {next_trunk_page}")
                break
            next_trunk_page = struct.unpack('>I', page_data[0:4])[0]
            n = struct.unpack('>I', page_data[4:8])[0]
            for i in range(n):
                offset = 8 + i*4
                if offset + 4 > len(page_data):
                    print(f"Insufficient data to read freelist leaf page at index {i} on page {next_trunk_page}")
                    break
                page_num = struct.unpack('>I', page_data[offset:offset + 4])[0]
                freelist_pages.append(page_num - 1)
                pages_collected += 1
    except Exception as e:
        print(f"Error reading freelist pages: {e}")
    return freelist_pages

def identify_image(blob_data):
    """
    Identifies if the BLOB data is an image by checking common image file signatures.
    Returns the image format if recognized, otherwise returns None.
    """
    signatures = {
        b'\xFF\xD8\xFF': 'jpg',  # JPEG
        b'\x89PNG\r\n\x1A\n': 'png',  # PNG
        b'GIF87a': 'gif',  # GIF87a
        b'GIF89a': 'gif',  # GIF89a
        b'BM': 'bmp',  # BMP
        b'II*\x00': 'tif',  # TIFF little-endian
        b'MM\x00*': 'tif',  # TIFF big-endian
        b'\x00\x00\x01\x00': 'ico',  # ICO
    }
    max_sig_len = max(len(sig) for sig in signatures)
    blob_start = blob_data[:max_sig_len]
    for sig, fmt in signatures.items():
        if blob_start.startswith(sig):
            return fmt
    return None

def main():
    parser = argparse.ArgumentParser(description='SQLite Forensic Data Recovery Tool')
    parser.add_argument('-i', '--input', required=True, help='Input SQLite database file')
    parser.add_argument('-o', '--output', required=True, help='Output file (SQLite database or CSV file)')
    parser.add_argument('-f', '--format', choices=['sqlite', 'csv'], default='sqlite', help='Output format: sqlite (default) or csv')
    parser.add_argument('-e', '--extract-images', action='store_true', help='Extract images from BLOB fields')
    parser.add_argument('-d', '--image-dir', default='images', help='Directory to save extracted images')
    args = parser.parse_args()

    source_filename = args.input
    output_filename = args.output
    output_format = args.format
    extract_images = args.extract_images
    image_dir = args.image_dir

    try:
        with open(source_filename, 'rb') as f:
            data = f.read()
    except Exception as e:
        print(f"Error reading input file: {e}")
        sys.exit(1)

    # Read the file header
    if len(data) < 100:
        print("File is too small to be a valid SQLite database.")
        sys.exit(1)

    file_header = data[:100]
    if file_header[:16] != b'SQLite format 3\x00':
        print("Not a valid SQLite 3 database file.")
        sys.exit(1)
    page_size = struct.unpack('>H', file_header[16:18])[0]
    if page_size == 1:
        page_size = 65536
    # Get freelist information
    freelist_trunk_page = struct.unpack('>I', file_header[32:36])[0]
    total_freelist_pages = struct.unpack('>I', file_header[36:40])[0]
    # Collect freelist pages
    freelist_pages = []
    if freelist_trunk_page != 0:
        freelist_pages = get_freelist_pages(data, page_size, freelist_trunk_page, total_freelist_pages)

    # Prepare to collect records
    records = []
    max_fields = 0
    # Parse all pages
    num_pages = len(data) // page_size
    for page_number in range(num_pages):
        parse_page(data, page_number, page_size, records)
    # Parse freelist pages separately if needed
    if freelist_pages:
        for page_number in freelist_pages:
            parse_page(data, page_number, page_size, records)
    else:
        print("No freelist pages found or an error occurred while reading freelist pages.")

    if not records:
        print("No records recovered.")
        sys.exit(1)

    # Determine the maximum number of fields
    for record in records:
        if len(record) > max_fields:
            max_fields = len(record)
    # Create image directory if extracting images
    if extract_images:
        if not os.path.exists(image_dir):
            os.makedirs(image_dir)
        image_counter = 1
    # Output the data
    if output_format == 'sqlite':
        # Create new database and create a generic table
        conn = sqlite3.connect(output_filename)
        cursor = conn.cursor()
        # Create generic table
        field_names = ', '.join([f'field{i+1}' for i in range(max_fields)])
        create_table_sql = f'CREATE TABLE recovered_data ({field_names})'
        cursor.execute(create_table_sql)
        # Insert records
        for record in records:
            num_fields = len(record)
            if num_fields < max_fields:
                record.extend([None] * (max_fields - num_fields))
            if extract_images:
                # Process each field to extract images
                for idx, value in enumerate(record):
                    if isinstance(value, bytes):
                        fmt = identify_image(value)
                        if fmt:
                            image_filename = f'image_{image_counter}.{fmt}'
                            image_path = os.path.join(image_dir, image_filename)
                            try:
                                with open(image_path, 'wb') as img_file:
                                    img_file.write(value)
                                record[idx] = image_filename  # Replace BLOB data with filename
                                image_counter += 1
                            except Exception as e:
                                print(f"Failed to save image: {e}")
                        else:
                            record[idx] = value.hex()
            placeholders = ', '.join(['?'] * max_fields)
            insert_sql = f'INSERT INTO recovered_data VALUES ({placeholders})'
            cursor.execute(insert_sql, record)
        conn.commit()
        conn.close()
        print(f"Data recovery complete. New SQLite database created at {output_filename}")
        if extract_images:
            print(f"Extracted images saved in '{image_dir}' directory.")
    elif output_format == 'csv':
        if extract_images and not os.path.exists(image_dir):
            os.makedirs(image_dir)
            image_counter = 1
        with open(output_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            # Write header
            header = [f'field{i+1}' for i in range(max_fields)]
            writer.writerow(header)
            # Write records
            for record in records:
                num_fields = len(record)
                if num_fields < max_fields:
                    record.extend([None] * (max_fields - num_fields))
                # Convert bytes to hex string for BLOB data
                formatted_record = []
                for value in record:
                    if isinstance(value, bytes):
                        if extract_images:
                            fmt = identify_image(value)
                            if fmt:
                                image_filename = f'image_{image_counter}.{fmt}'
                                image_path = os.path.join(image_dir, image_filename)
                                try:
                                    with open(image_path, 'wb') as img_file:
                                        img_file.write(value)
                                    formatted_record.append(image_filename)
                                    image_counter += 1
                                except Exception as e:
                                    print(f"Failed to save image: {e}")
                                    formatted_record.append(value.hex())
                            else:
                                formatted_record.append(value.hex())
                        else:
                            formatted_record.append(value.hex())
                    else:
                        formatted_record.append(value)
                writer.writerow(formatted_record)
        print(f"Data recovery complete. CSV file created at {output_filename}")
        if extract_images:
            print(f"Extracted images saved in '{image_dir}' directory.")

if __name__ == '__main__':
    main()
