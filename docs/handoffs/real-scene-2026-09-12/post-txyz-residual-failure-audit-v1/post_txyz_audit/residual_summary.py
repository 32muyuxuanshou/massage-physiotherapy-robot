import collections, statistics
from .frame_outcomes import classify_frame

def describe(rows, feature_rows):
    groups=collections.defaultdict(list)
    for row,features in zip(rows,feature_rows):groups[classify_frame(row)["frame_outcome_class"]].append(features)
    output={}
    for group,items in groups.items():
        values={}
        for name in items[0]:
            present=[item[name]["value"] for item in items if item[name]["value"] is not None]
            if present and all(isinstance(x,(int,float)) and not isinstance(x,bool) for x in present):values[name]={"count":len(present),"median":statistics.median(present),"min":min(present),"max":max(present)}
        output[group]={"count":len(items),"descriptive_only":True,"features":values}
    return output
