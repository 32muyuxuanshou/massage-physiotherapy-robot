import importlib.util
import json


modules = ["numpy", "PIL", "OpenImageIO", "cv2"]
print(json.dumps({name: importlib.util.find_spec(name) is not None for name in modules}, ensure_ascii=False))

import OpenImageIO as oiio
print("OIIO", oiio.VERSION_STRING)
print("TypeDesc attrs", [name for name in dir(oiio.TypeDesc) if "UINT8" in name.upper() or "FLOAT" in name.upper()])
print("ImageOutput", [name for name in dir(oiio.ImageOutput) if "write" in name.lower()])
print("module types", [(name, repr(getattr(oiio, name))) for name in dir(oiio) if name in {"UINT8", "FLOAT", "HALF"}])
