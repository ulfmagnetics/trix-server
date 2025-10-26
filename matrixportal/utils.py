import gc
from displayio import Bitmap
from config import DEBUG

def bitmap_from_bytes(bmp_data: bytes, source_name: str = "bytes") -> Bitmap:
    """
    Create a Bitmap instance by parsing BMP data from bytes.
    This allows loading BMPs from network requests, files, or any bytes source.

    Args:
        bmp_data: Raw BMP file data as bytes
        source_name: Optional name for debug output (e.g., filename or URL)

    Returns:
        Bitmap object containing the parsed image data
    """
    # Validate BMP data
    if len(bmp_data) < 138:
        raise ValueError("BMP data too short")

    # Parse header
    bmp_header_bytes = bmp_data[0:138]

    if bmp_header_bytes[0:2] != b"BM":
        raise ValueError(f"Invalid BMP file - missing BM signature: {bmp_header_bytes[0:2]}")

    bmp_header = memoryview(bmp_header_bytes).cast("H")

    data_offset = read_word(bmp_header, 5)
    header_size = read_word(bmp_header, 7)
    if header_size != 40:
        raise ValueError(f"Unsupported BMP header format: {header_size}")

    # struct BitmapInfoHeaderV1 {
    #     u32 biSize;
    #     s32 biWidth;
    #     s32 biHeight;
    #     u16 biPlanes;
    #     u16 biBitCount;
    #     Compression biCompression;
    #     u32 biSizeImage;
    #     s32 biXPelsPerMeter;
    #     s32 biYPelsPerMeter;
    #     u32 biClrUsed;
    #     u32 biClrImportant;
    # };
    width = read_word(bmp_header, 9)
    height = read_word(bmp_header, 11)
    bits_per_pixel = bmp_header[14]

    _debug_print(f"Loading BMP: {source_name}")
    _debug_print(f"  Width: {width}px")
    _debug_print(f"  Height: {height}px")
    _debug_print(f"  Bits per pixel: {bits_per_pixel}")
    _debug_print(f"  Data offset: {data_offset}")
    _debug_print(f"  Header size: {header_size}")

    # Calculate value_count for Bitmap constructor
    if bits_per_pixel <= 8:
        value_count = 1 << bits_per_pixel
    else:
        value_count = 65536  # Max for RGB values

    _debug_print(f"  Value count: {value_count}")

    # Create the bitmap
    bitmap = Bitmap(width, height, value_count)

    # Read pixel data and populate bitmap
    bytes_per_pixel = max(1, bits_per_pixel // 8)
    pixels_per_byte = 8 // bits_per_pixel if bits_per_pixel < 8 else 1

    # Calculate stride (BMP rows are padded to 4-byte boundaries)
    if bits_per_pixel < 8:
        bit_stride = width * bits_per_pixel
        if bit_stride % 32 != 0:
            bit_stride += 32 - bit_stride % 32
        stride = bit_stride // 8
    else:
        stride = width * bytes_per_pixel
        if stride % 4 != 0:
            stride += 4 - stride % 4

    _debug_print(f"  Stride: {stride} bytes")
    _debug_print(f"  Bytes per pixel: {bytes_per_pixel}")

    # Read pixel data (BMP rows are stored bottom-to-top)
    for y in range(height):
        bmp_row = height - y - 1  # BMP stores rows inverted
        row_start = data_offset + bmp_row * stride
        row_end = row_start + stride
        row_data = bmp_data[row_start:row_end]

        for x in range(width):
            if bits_per_pixel == 8:
                pixel_value = row_data[x]
            elif bits_per_pixel == 4:
                byte_idx = x // 2
                if x % 2 == 0:
                    pixel_value = (row_data[byte_idx] >> 4) & 0x0F
                else:
                    pixel_value = row_data[byte_idx] & 0x0F
            elif bits_per_pixel == 1:
                byte_idx = x // 8
                bit_idx = 7 - (x % 8)
                pixel_value = (row_data[byte_idx] >> bit_idx) & 1
            elif bits_per_pixel == 16:
                # 16-bit RGB565 format
                # BMP stores as little-endian 16-bit values
                byte_idx = x * 2
                pixel_value = row_data[byte_idx] | (row_data[byte_idx + 1] << 8)
            elif bits_per_pixel == 24:
                # 24-bit RGB888 format
                # BMP stores pixels as BGR (blue, green, red)
                byte_idx = x * 3
                b = row_data[byte_idx + 0]
                g = row_data[byte_idx + 1]
                r = row_data[byte_idx + 2]
                # Convert RGB888 to RGB565 (5 bits red, 6 bits green, 5 bits blue)
                r5 = (r >> 3) & 0x1F  # 8-bit to 5-bit
                g6 = (g >> 2) & 0x3F  # 8-bit to 6-bit
                b5 = (b >> 3) & 0x1F  # 8-bit to 5-bit
                pixel_value = (r5 << 11) | (g6 << 5) | b5
            elif bits_per_pixel == 32:
                # 32-bit RGBA/RGBX format
                # BMP stores pixels as BGRA/BGRX
                byte_idx = x * 4
                b = row_data[byte_idx + 0]
                g = row_data[byte_idx + 1]
                r = row_data[byte_idx + 2]
                # Convert RGB888 to RGB565 (ignore alpha/padding byte)
                r5 = (r >> 3) & 0x1F  # 8-bit to 5-bit
                g6 = (g >> 2) & 0x3F  # 8-bit to 6-bit
                b5 = (b >> 3) & 0x1F  # 8-bit to 5-bit
                pixel_value = (r5 << 11) | (g6 << 5) | b5
            else:
                # Unsupported format
                pixel_value = 0

            bitmap[x, y] = pixel_value

    return bitmap

def bitmap_from_bmp_file(filename: str) -> Bitmap:
    """
    Create a Bitmap instance by reading and parsing a BMP file from disk.

    Args:
        filename: Path to the BMP file

    Returns:
        Bitmap object containing the parsed image data
    """
    with open(filename, "rb") as file:
        bmp_data = file.read()

    return bitmap_from_bytes(bmp_data, source_name=filename)

def read_word(header: memoryview, index: int) -> int:
    """Read a 32-bit value from a memoryview cast as 16-bit values"""
    return header[index] | header[index + 1] << 16

def dump_mem_usage():
    gc.collect()
    free = gc.mem_free()
    allocated = gc.mem_alloc()
    total = free + allocated
    print(f"Free: {free/1023:.1f} KB")
    print(f"Used: {allocated/1023:.1f} KB")
    print(f"Total: {total/1023:.1f} KB")

def _debug_print(msg: str) -> None:
    """Print debug message if DEBUG mode is enabled."""
    if DEBUG:
        print(msg)