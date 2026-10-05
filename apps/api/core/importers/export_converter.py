"""Preserve localized descriptions when converting ocldev 0.2.3 exports."""
from ocldev.oclexporttoimportconverter import OCLExportToImportConverter as UpstreamExportConverter


class OCLExportToImportConverter(UpstreamExportConverter):
    """Keep the upstream conversion, correcting its empty description iteration.

    Remove this override when a pinned ocldev release passes the ZIP regression
    cases. Ownership, sources, names, mappings and version conversion remain
    implemented by the upstream converter. See the monorepo UPSTREAM.md.
    """

    def get_concepts_data(self):
        """Strip server-generated locale metadata while retaining every description."""
        concepts = super().get_concepts_data()
        for converted, original in zip(concepts, self.get('concepts', []), strict=True):
            converted['descriptions'] = [
                {key: value for key, value in description.items()
                 if key not in ('uuid', 'checksum', 'checksums', 'type')}
                for description in original.get('descriptions') or []
            ]
        return concepts
