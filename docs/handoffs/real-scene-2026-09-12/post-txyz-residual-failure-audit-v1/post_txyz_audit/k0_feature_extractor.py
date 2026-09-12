import math

def extract_existing(row, schema):
    t=[float(x)*1000 for x in row["Txyz_m"]];known={"tx_mm":t[0],"ty_mm":t[1],"tz_mm":t[2],"translation_norm_mm":math.sqrt(sum(x*x for x in t)),"fallback":bool(row["fallback"]),"sam_runtime_ms":float(row["runtime_sam_ms"]),"txyz_runtime_ms":float(row["runtime_txyz_ms"]),"total_runtime_ms":float(row["runtime_total_ms"])}
    output={}
    for feature in schema:
        name=feature["name"]
        if name in known:output[name]={"status":"AVAILABLE_NOW","value":known[name]}
        else:output[name]={"status":feature["availability_status"],"value":None}
    return output
