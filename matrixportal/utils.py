import gc
from displayio import Bitmap
from config import DEBUG

def _debug_print(msg: str) -> None:
    """Print debug message if DEBUG mode is enabled."""
    if DEBUG:
        print(msg)

def bitmap_from_bmp_file(filename: str) -> Bitmap:
    """
    Create a Bitmap instance by reading and parsing a BMP file.
    Adapted from the Adafruit Blinka codebase.
    """
    with open(filename, "rb") as file:
        file.seek(0)
        bmp_header = memoryview(file.read(138)).cast("H")
        
        if len(bmp_header.tobytes()) != 138 or bmp_header.tobytes()[0:2] != b"BM":
            raise ValueError("Invalid BMP file")
        
        data_offset = read_word(bmp_header, 5)
        header_size = read_word(bmp_header, 7)
        bits_per_pixel = bmp_header[14]
        width = read_word(bmp_header, 9)
        height = read_word(bmp_header, 11)

        _debug_print(f"Loading BMP: {filename}")
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
            file.seek(data_offset + bmp_row * stride)
            row_data = file.read(stride)
            
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
                    b = row_data[byte_idx]
                    g = row_data[byte_idx + 1]
                    r = row_data[byte_idx + 2]
                    # Pack as 0xRRGGBB
                    pixel_value = (r << 16) | (g << 8) | b
                elif bits_per_pixel == 32:
                    # 32-bit RGBA/RGBX format
                    # BMP stores pixels as BGRA/BGRX
                    byte_idx = x * 4
                    b = row_data[byte_idx]
                    g = row_data[byte_idx + 1]
                    r = row_data[byte_idx + 2]
                    # Ignore alpha/padding byte, pack as RGB888
                    pixel_value = (r << 16) | (g << 8) | b
                else:
                    # Unsupported format
                    pixel_value = 0

                bitmap[x, y] = pixel_value
        
        return bitmap

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