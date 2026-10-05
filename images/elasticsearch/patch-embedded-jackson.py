"""Update the embedded provider using the complete upstream patch artifact.

Elasticsearch embeds expanded JARs under IMPL-JARS and names them in LISTING.TXT.
Replacing the external classpath JAR alone leaves those private copies intact.
"""
import hashlib
from pathlib import Path
import urllib.request
from zipfile import ZipFile, ZIP_DEFLATED

OLD = 'jackson-core-2.21.6.jar'
NEW = 'jackson-core-2.21.7.jar'
PREFIX = 'IMPL-JARS/x-content/'


def main():
    """Fail if upstream packaging changes instead of silently missing a copy."""
    for line in Path('/work/jackson.sha256').read_text().splitlines():
        checksum, filename = line.split()
        artifact = filename.removesuffix('-2.21.7.jar')
        url = f'https://repo.maven.apache.org/maven2/com/fasterxml/jackson/core/{artifact}/2.21.7/{filename}'
        data = urllib.request.urlopen(url, timeout=60).read()
        if hashlib.sha256(data).hexdigest() != checksum:
            raise ValueError('Artifact checksum mismatch: ' + filename)
        Path('/work', filename).write_bytes(data)

    archives = sorted(Path('/patched').rglob('*.jar'))
    if len(archives) != 2:
        raise ValueError('Expected two Elasticsearch provider archives.')
    for path in archives:
        target = path.with_suffix('.patched')
        with ZipFile(path) as original, ZipFile('/work/' + NEW) as replacement, \
                ZipFile(target, 'w', ZIP_DEFLATED) as output:
            listing = PREFIX + 'LISTING.TXT'
            listed = original.read(listing).decode().splitlines()
            if listed.count(OLD) != 1 or not any(n.startswith(PREFIX + OLD + '/') for n in original.namelist()):
                raise ValueError('Unexpected embedded provider layout: ' + str(path))
            for entry in original.infolist():
                if entry.filename.startswith(PREFIX + OLD + '/'):
                    continue
                data = original.read(entry)
                if entry.filename == listing:
                    data = data.replace(OLD.encode(), NEW.encode())
                output.writestr(entry, data)
            for entry in replacement.infolist():
                output.writestr(PREFIX + NEW + '/' + entry.filename, replacement.read(entry))
            output.comment = original.comment
        target.replace(path)
        print('Updated embedded provider:', path)


if __name__ == '__main__':
    main()
