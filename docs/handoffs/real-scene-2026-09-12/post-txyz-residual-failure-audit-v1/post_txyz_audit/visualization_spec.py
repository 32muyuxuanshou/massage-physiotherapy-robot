def paths(frame_id):
    safe=frame_id.replace('/','_')
    return {"server_only_rgb_bundle":f"failure_cases/{safe}/visualization_manifest.json","public_numeric_plot":f"plots/{safe}_k0_features.png","server_bundle_contains_behave_rgb":True,"public_plot_contains_behave_rgb":False}
