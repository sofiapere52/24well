"""Hardware visibility check. Never enables HS5 output and never routes a well.

  python tools/check_hardware.py                 list TiePie devices and COM ports
  python tools/check_hardware.py --open-hs5      also open/close each HS5 generator (output stays off)
  python tools/check_hardware.py --arduino COM5  also HELLO/PING/STATUS and OFF 0 (all wells off)
"""
import argparse
import sys
import time

ARDUINO_VIDS = {0x2341, 0x2A03}


def tiepie(open_hs5):
    import libtiepie as lt
    lt.network.auto_detect_enabled = False
    lt.device_list.update()
    items = list(lt.device_list)
    print(f'TiePie devices usable by this program: {len(items)}')
    for item in items:
        print(f'  {item.name}  serial {item.serial_number}  generator={item.can_open(lt.DEVICETYPE_GENERATOR)}')
        if open_hs5 and item.can_open(lt.DEVICETYPE_GENERATOR):
            gen = item.open_generator()
            try: print(f'    opened OK, output_enable={gen.output_enable}, amplitude range '
                       f'{gen.amplitude_min:g}-{gen.amplitude_max:g} V')
            finally: del gen
    if not items:
        print('  None. If Windows lists "Handyscope HS5" in Device Manager, another program has it open '
              '(HS5 GUI, MATLAB, TiePie Multi Channel). Close it and run this again.')


def ports():
    from serial.tools import list_ports
    found = list(list_ports.comports())
    print(f'COM ports: {len(found)}')
    for p in found:
        tag = '  <- Arduino' if p.vid in ARDUINO_VIDS else ''
        print(f'  {p.device}: {p.description}{tag}')
    if not any(p.vid in ARDUINO_VIDS for p in found):
        print('  No Arduino found. Connect the Arduino DUE "Programming" USB port (next to the power jack) to this PC.')


def arduino(port):
    import serial
    with serial.Serial(port, 9600, timeout=.1, write_timeout=1) as s:
        time.sleep(2)  # opening the port resets the DUE
        s.reset_input_buffer()
        for n, op in enumerate(('HELLO', 'PING', 'STATUS', 'OFF 0'), 1):
            s.write(f'{n} {op}\n'.encode('ascii'))
            deadline, reply = time.monotonic() + 1.5, ''
            while time.monotonic() < deadline and not reply.startswith(f'{n} '):
                reply = s.readline().decode('ascii', errors='replace').strip()
            print(f'  {op:7} -> {reply or "NO REPLY (wrong port, wrong firmware, or not powered)"}')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--open-hs5', action='store_true')
    parser.add_argument('--arduino', metavar='COMx')
    args = parser.parse_args()
    tiepie(args.open_hs5)
    ports()
    if args.arduino:
        print(f'Arduino on {args.arduino}:')
        arduino(args.arduino)
    return 0


if __name__ == '__main__':
    sys.exit(main())
