# -*- coding: utf-8 -*-

from io import StringIO, BufferedReader
import os
import string
import py
import pytest
from hashfs import HashFS, unshard


@pytest.fixture
def testpath(tmpdir):
    return tmpdir.mkdir('hashfs')


@pytest.fixture
def testfile(testpath):
    return testpath.join('hashfs.txt')


@pytest.fixture
def stringio():
    return StringIO(u'foo')


@pytest.yield_fixture
def fileio(testfile):
    with open(str(testfile), 'wb') as io:
        io.write(b'foo')

    io = open(str(testfile), 'rb')
    yield io
    io.close()


@pytest.fixture
def filepath(testfile):
    testfile.write(b'foo')
    return testfile


@pytest.fixture
def fs(testpath):
    return HashFS(str(testpath))


@pytest.fixture
def fs_relative():
    return HashFS('relative_path')


@pytest.fixture
def fssha1(testpath):
    return HashFS(str(testpath), algorithm='sha1')


def put_range(fs, count):
    return dict((address.abspath, address)
                for address in (fs.put(StringIO(u'{0}'.format(i)))
                                for i in range(count)))


def assert_file_put(fs, address):
    directory = os.path.dirname(address.abspath)
    reldirectory = str(directory).split(str(fs.root))[-1]
    dir_parts = [part for part in reldirectory.split(os.path.sep) if part]

    assert address.abspath in tuple(py.path.local(fs.root).visit())
    assert fs.exists(address.digest)

    digest = str(address.abspath).split(os.path.sep)[-1]
    assert digest == address.digest

    assert len(dir_parts) == fs.depth
    assert all(len(part) == fs.width for part in dir_parts)


def test_hashfs_put_stringio(fs, stringio):
    address = fs.put(stringio)
    assert_file_put(fs, address)
    with open(address.abspath, 'rb') as fileobj:
        assert fileobj.read() == bytes(stringio.getvalue(), 'UTF8')


def test_hashfs_put_fileobj(fs, fileio):
    address = fs.put(fileio)

    assert_file_put(fs, address)

    with open(address.abspath, 'rb') as fileobj:
        assert fileobj.read() == fileio.read()


def test_hashfs_put_file(fs, filepath):
    address = fs.put(str(filepath))

    assert_file_put(fs, address)

    with open(address.abspath, 'rb') as fileobj:
        assert fileobj.read() == bytes(filepath.read(), 'UTF8')


def test_hashfs_put_duplicate(fs, stringio):
    address_a = fs.put(stringio)
    address_b = fs.put(stringio)

    assert not address_a.is_duplicate
    assert address_b.is_duplicate


def test_hashfs_put_error(fs):
    with pytest.raises(ValueError):
        fs.put('foo')


def test_hashfs_address(fs, stringio):
    address = fs.put(stringio)

    assert str(fs.root) in address.abspath
    assert address.abspath.split(os.path.sep)[-1] == address.digest
    assert not address.is_duplicate


@pytest.mark.parametrize('address_attr', [
    ('digest'),
    ('digest'),
    ('digest'),
])
def test_hashfs_open(fs, stringio, address_attr):
    address = fs.put(stringio)

    fileobj = fs.open(getattr(address, address_attr))

    assert isinstance(fileobj, BufferedReader)
    assert fileobj.read() == bytes(stringio.getvalue(), 'UTF8')

    fileobj.close()


def test_hashfs_open_error(fs):
    with pytest.raises(ValueError):
        fs.open('invalid')


def test_hashfs_exists(fs, stringio):
    address = fs.put(stringio)
    assert fs.exists(address.digest)


def test_hashfs_contains(fs, stringio):
    address = fs.put(stringio)
    assert address.digest in fs


def test_hashfssh1_contains(fssha1, stringio):
    address = fssha1.put(stringio)
    assert fssha1.algorithm == 'sha1'
    assert address.digest in fssha1


def test_hashfs_relative(fs_relative):
    assert os.path.sep in str(fs_relative.root)
    assert str(fs_relative.root).startswith(os.path.sep)


def test_hashfs_get(fs, stringio):
    address = fs.put(stringio)

    assert not address.is_duplicate
    assert fs.get(address.digest) == address
    with pytest.raises(ValueError):
        fs.get('invalid')

    with pytest.raises(ValueError):
        fs.get('0' * (fs.digestlen + 1))
    with pytest.raises(ValueError):
        fs.get('0' * (fs.digestlen - 1))
    with pytest.raises(FileNotFoundError):
        fs.get('0' * fs.digestlen)


@pytest.mark.parametrize('address_attr', [
    'digest',
])
def test_hashfs_delete(fs, stringio, address_attr):
    address = fs.put(stringio)

    fs.delete(getattr(address, address_attr))
    assert len(os.listdir(fs.root)) == 1


def test_hashfs_delete_error(fs):
    with pytest.raises(ValueError):
        fs.delete('invalid')
    with pytest.raises(ValueError):
        fs.delete('0' * (fs.digestlen + 1))
    with pytest.raises(ValueError):
        fs.delete('0' * (fs.digestlen - 1))
    with pytest.raises(FileNotFoundError):
        fs.delete('0' * fs.digestlen)
    with pytest.raises(ValueError):
        fs.delete(('0' * (fs.digestlen - 1)) + 'z')


def test_hashfs_unshard(fs, stringio):
    address = fs.put(stringio)
    assert unshard(address.abspath) == address.digest


def test_hashfs_unshard_error(fs):
    with pytest.raises(ValueError):
        unshard('invalid')


def test_hashfs_digestpath(fs):
    assert fs.digestpath('0' * fs.digestlen) == str(fs.root) + os.path.sep + \
        os.path.sep.join(list('0' * fs.depth)) + os.path.sep + \
        ('0' * fs.digestlen)
    with pytest.raises(ValueError):
        fs.digestpath('invalid')
    with pytest.raises(ValueError):
        fs.digestpath('0' * (fs.digestlen + 1))
    with pytest.raises(ValueError):
        fs.digestpath('0' * (fs.digestlen - 1))
    with pytest.raises(ValueError):
        fs.digestpath(('0' * (fs.digestlen - 1)) + 'z')


def test_hashfs_files(fs):
    count = 5
    addresses = put_range(fs, count)
    files = list(fs.files())

    assert len(files) == count

    for file in files:
        assert os.path.isfile(file)
        assert file in addresses
        assert addresses[file].abspath == file
        assert addresses[file].digest == unshard(file)


def test_hashfs_iter(fs):
    count = 5
    addresses = put_range(fs, count)
    test_count = 0

    for file in fs:
        test_count += 1
        assert os.path.isfile(file)
        assert file in addresses
        assert addresses[file].abspath == file
        assert addresses[file].digest == unshard(file)

    assert test_count == count


def test_hashfs_corrupted(fs, stringio):
    address = fs.put(stringio)
    with open(address.abspath, 'ab') as fh:
        fh.write(b'f')
    assert len(list(fs.corrupted())) == 1


def test_hashfs_count(fs):
    count = 5
    put_range(fs, count)
    assert fs.count() == count


def test_hashfs_len(fs):
    count = 5
    put_range(fs, count)
    assert len(fs) == count


def test_hashfs_size(fs):
    fs.put(StringIO(u'{0}'.format(string.ascii_lowercase)))
    fs.put(StringIO(u'{0}'.format(string.ascii_uppercase)))
    expected = len(string.ascii_lowercase) + len(string.ascii_uppercase)

    assert fs.size() == expected
