import asyncio
import hashlib
import binascii
from bitcoin import deserialize, serialize, decode, bin_sha256, encode

from spruned.application import exceptions


def normalize_transaction(tx):
    _tx = deserialize(tx)
    _tx['segwit'] = True
    for i, vin in enumerate(_tx['ins']):
        if vin.get('txinwitness', '0'*64) == '0'*64:
            _tx['ins'][i]['txinwitness'] = ''
    return serialize(_tx)


def blockheader_to_blockhash(header: (bytes, str)) -> (bytes, str):
    if isinstance(header, bytes):
        h, fmt = header, 'bin'
    else:
        h, fmt = binascii.unhexlify(header.encode()), 'hex'
    blockhash = hashlib.sha256(hashlib.sha256(h).digest())
    bytes_blockhash = blockhash.digest()[::-1]
    return fmt == 'hex' and binascii.hexlify(bytes_blockhash).decode() or bytes_blockhash


def deserialize_header(header: (str, bytes)):
    if isinstance(header, bytes):
        h, fmt = header, 'bin'
    else:
        h, fmt = binascii.unhexlify(header.encode()), 'hex'
    blockhash = bin_sha256(bin_sha256(h))[::-1]
    data = {
        "version": decode(h[:4][::-1], 256),
        "prev_block_hash": h[4:36][::-1],
        "merkle_root": h[36:68][::-1],
        "timestamp": decode(h[68:72][::-1], 256),
        "bits": decode(h[72:76][::-1], 256),
        "nonce": decode(h[76:80][::-1], 256),
        "hash": blockhash
    }
    if fmt == 'hex':
        data['prev_block_hash'] = binascii.hexlify(data['prev_block_hash']).decode()
        data['merkle_root'] = binascii.hexlify(data['merkle_root']).decode()
        data['hash'] = binascii.hexlify(data['hash']).decode()
    verify_pow(h, blockhash)
    return data


def verify_pow(header, blockhash):
    bits = header[72:76][::-1]
    target = int.from_bytes(bits[1:], 'big') * 2 ** (8 * (bits[0] - 3))
    if target < int.from_bytes(blockhash, 'little'):
        return True
    raise exceptions.InvalidPOWException


def serialize_header(inp):
    o = encode(inp['version'], 256, 4)[::-1] + \
        binascii.unhexlify(inp['prev_block_hash'])[::-1] + \
        binascii.unhexlify(inp['merkle_root'])[::-1] + \
        encode(inp['timestamp'], 256, 4)[::-1] + \
        encode(inp['bits'], 256, 4)[::-1] + \
        encode(inp['nonce'], 256, 4)[::-1]
    h = binascii.hexlify(bin_sha256(bin_sha256(o))[::-1]).decode()
    if inp.get('hash'):
        assert h == inp['hash'], (hashlib.sha256(o), inp['hash'])
    return binascii.hexlify(o).decode()


def get_nearest_parent(number: int, divisor: int):
    return int(number - number % divisor)


async def async_delayed_task(task, seconds: int=0, disable_log=False):
    from spruned.application.logging_factory import Logger
    not disable_log and Logger.root.debug('Scheduling task %s in %s seconds', task, seconds)
    await asyncio.sleep(seconds)
    return await task


def decode_raw_transaction(rawtx: str):
    tx = deserialize(rawtx)
    pass


def load_config():
    """
    todo: parse config or create with default values
    """
    from spruned import settings
    import os
    if not os.path.exists(settings.FILE_DIRECTORY):
        os.makedirs(settings.FILE_DIRECTORY)
    if not os.path.exists(settings.STORAGE_ADDRESS):
        os.makedirs(settings.STORAGE_ADDRESS)
    if not os.path.exists(settings.SQLITE_DBNAME):
        os.makedirs(settings.SQLITE_DBNAME)


def check_internet_connection():
    from spruned.application.logging_factory import Logger
    from spruned.settings import CHECK_NETWORK_HOST
    import subprocess
    import os
    Logger.electrum.debug('Checking internet connectivity')
    i = 0
    while i < 10:
        import random
        host = random.choice(CHECK_NETWORK_HOST)
        ret_code = subprocess.call(['ping', '-c', '1', '-W', '5', host],
                                   stdout=open(os.devnull, 'w'),
                                   stderr=open(os.devnull, 'w'))
        if not ret_code:
            return True
        i += 1
    Logger.electrum.debug('No internet connectivity!')
    return False

