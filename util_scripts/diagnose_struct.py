"""Diagnostic script to investigate CNC_JOB_STATUS struct alignment.

Run this on the CNC machine while a job is loaded to compare
the raw struct bytes against the Python field definitions.
"""
import ctypes
import struct
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ctypes import sizeof, c_int, c_double, c_wchar, c_char
from cncapi.python.cncstructs import CNC_JOB_STATUS
from cncapi.python.cncenums import CNC_MAX_PATH, CNC_MAX_INTERPRETER_LINE


def main():
    print("=" * 70)
    print("CNC_JOB_STATUS Struct Diagnostic")
    print("=" * 70)

    # 1. Print constants
    print(f"\nCNC_MAX_PATH = {CNC_MAX_PATH}")
    print(f"CNC_MAX_INTERPRETER_LINE = {CNC_MAX_INTERPRETER_LINE}")
    print(f"sizeof(c_wchar) = {sizeof(c_wchar)}")
    print(f"sizeof(c_int) = {sizeof(c_int)}")
    print(f"sizeof(c_double) = {sizeof(c_double)}")

    # 2. Print Python struct info
    print(f"\nPython sizeof(CNC_JOB_STATUS) = {sizeof(CNC_JOB_STATUS)}")
    print(f"Python _pack_ = {CNC_JOB_STATUS._pack_}")

    # 3. Print field offsets and sizes
    print(f"\n{'Field':<40} {'Offset':>6} {'Size':>6} {'Type'}")
    print("-" * 70)
    for field_name, field_type in CNC_JOB_STATUS._fields_:
        field_obj = getattr(CNC_JOB_STATUS, field_name)
        offset = field_obj.offset
        size = field_obj.size
        print(f"{field_name:<40} {offset:>6} {size:>6}   {field_type.__name__}")

    # 4. Try to connect and read actual data
    print("\n" + "=" * 70)
    print("Attempting to read live data from CNC DLL...")
    print("=" * 70)

    try:
        from src.core.config import Settings
        settings = Settings()
        dll = ctypes.WinDLL(settings.dll_path)

        # Connect
        dll.CncConnectServer.argtypes = [ctypes.c_char_p]
        dll.CncConnectServer.restype = ctypes.c_int
        rc = dll.CncConnectServer(settings.ini_path.encode("ascii"))
        print(f"CncConnectServer() = {rc}")

        if rc not in (0, 6, 7):
            print("Failed to connect, can't read live data")
            return

        # Get job status as raw pointer
        dll.CncGetJobStatus.argtypes = []
        dll.CncGetJobStatus.restype = ctypes.POINTER(CNC_JOB_STATUS)

        ptr = dll.CncGetJobStatus()
        s = ptr.contents

        # Dump raw bytes of the struct
        raw = ctypes.string_at(ptr, sizeof(CNC_JOB_STATUS) + 64)  # read 64 extra bytes

        print(f"\nRaw struct bytes ({len(raw)} bytes):")
        print(f"  First 32 after jobName (offset 520): {raw[520:552].hex()}")

        # 5. Print each field value vs what raw bytes say
        print(f"\n{'Field':<40} {'Offset':>6} {'Value'}")
        print("-" * 70)

        for field_name, field_type in CNC_JOB_STATUS._fields_:
            field_obj = getattr(CNC_JOB_STATUS, field_name)
            offset = field_obj.offset
            size = field_obj.size

            value = getattr(s, field_name)

            # Format value
            if isinstance(value, bytes):
                display = repr(value[:40])
            elif isinstance(value, str):
                display = repr(value[:60])
            else:
                display = repr(value)

            # Also show raw hex for suspicious fields
            raw_hex = raw[offset:offset+size].hex()
            if size <= 16:
                print(f"{field_name:<40} {offset:>6}   {display}  [{raw_hex}]")
            else:
                print(f"{field_name:<40} {offset:>6}   {display}")

        # 6. Probe beyond struct boundary for extra fields
        struct_size = sizeof(CNC_JOB_STATUS)
        print(f"\n{'Probing beyond struct boundary'}")
        print(f"Struct ends at offset {struct_size}")
        print(f"  +0  bytes (hex): {raw[struct_size:struct_size+8].hex()}")
        print(f"  +8  bytes (hex): {raw[struct_size+8:struct_size+16].hex()}")
        print(f"  +16 bytes (hex): {raw[struct_size+16:struct_size+24].hex()}")
        print(f"  +24 bytes (hex): {raw[struct_size+24:struct_size+32].hex()}")

        # Try reading extra bytes as int/double
        for extra_offset in [0, 4, 8, 12, 16, 20, 24]:
            pos = struct_size + extra_offset
            if pos + 8 <= len(raw):
                val_int = struct.unpack_from('<i', raw, pos)[0]
                val_double = struct.unpack_from('<d', raw, pos)[0]
                print(f"  +{extra_offset}: int={val_int}, double={val_double}")

        # 7. Key diagnostic: scan for the known garbage value 3158893
        # to find its true location in the raw bytes
        target_bytes = struct.pack('<i', 3158893)
        print(f"\nSearching for lastKnownToolChangeLineNumber=3158893 ({target_bytes.hex()}) in raw bytes:")
        for i in range(len(raw) - 4):
            if raw[i:i+4] == target_bytes:
                print(f"  Found at raw offset {i} (Python expects it at offset 632)")

        # 8. Scan for stockDiameterTurning garbage pattern
        target_double = struct.pack('<d', 5.432309226136e-312)
        print(f"\nSearching for stockDiameterTurning=5.432e-312 ({target_double.hex()}) in raw bytes:")
        for i in range(len(raw) - 8):
            if raw[i:i+8] == target_double:
                print(f"  Found at raw offset {i} (Python expects it at offset 1703)")

    except ImportError:
        print("Could not import Settings - run from project root")
    except OSError as e:
        print(f"DLL error: {e}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
