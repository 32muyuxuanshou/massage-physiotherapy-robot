from pathlib import Path

def resolve_k0(sequence_root,spec,file_ids):
    frame=Path(sequence_root)/spec['sequence']/spec['frame'];paths={name:frame/file_ids[name] for name in ('rgb','depth','mask')};missing=[str(path) for path in paths.values() if not path.is_file()]
    if missing:raise FileNotFoundError('K0_SOURCE_FILES_MISSING '+repr(missing))
    return {name:str(path.resolve()) for name,path in paths.items()}
