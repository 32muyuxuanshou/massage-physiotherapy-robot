"""Simplified-Chinese UI for Blender and the official SMPL-X extension.

Only user-facing labels and tooltips are translated.  Model object names,
armature bone names, shape-key identifiers and exported data remain unchanged.
"""

import bpy


TRANSLATION_DOMAIN = "smpl_acupoint_doctor_ui_zh_hans"


_ZH_HANS = {
    # Official SMPL-X sidebar and model selector.
    ("*", "SMPL Models"): "SMPL 模型",
    ("*", "SMPL Body Models"): "SMPL 人体模型",
    ("*", "Type"): "模型类型",
    ("*", "Body model type"): "人体模型类型",
    ("*", "Version"): "模型版本",
    ("*", "SMPL-X version"): "SMPL-X 模型版本",
    ("*", "Body"): "性别",
    ("*", "Body to load"): "要载入的人体性别",
    ("*", "SMPL-X Locked Head"): "SMPL-X 锁定头部版",
    ("*", "SMPL-X locked head model without head bun"): "无头顶发髻伪影的 SMPL-X 模型",
    ("*", "SMPL-X v1.1 model with head bun"): "带头顶发髻的 SMPL-X v1.1 模型",
    ("*", "Female"): "女性",
    ("*", "Male"): "男性",
    ("*", "Neutral"): "中性",
    ("*", "None"): "无",
    ("*", "Add"): "添加人体",
    ("*", "Add body model of selected gender to scene"): "将所选性别的人体模型添加到场景",
    ("*", "Body model not installed"): "人体模型尚未安装",
    ("*", "Texture:"): "皮肤纹理：",
    ("*", "Model texture"): "人体模型纹理",
    ("*", "Set"): "应用",
    ("*", "Set selected texture"): "应用所选皮肤纹理",
    ("*", "Female (UV 2023)"): "女性纹理（UV 2023）",
    ("*", "Male (UV 2023)"): "男性纹理（UV 2023）",
    ("*", "Female (UV 2021)"): "女性纹理（UV 2021）",
    ("*", "Male (UV 2021)"): "男性纹理（UV 2021）",
    ("*", "Rainbow (UV 2021)"): "彩虹纹理（UV 2021）",
    ("*", "UV Grid"): "UV 网格",
    ("*", "Color Grid"): "彩色网格",

    # Shape / body measurements.
    ("*", "Shape"): "体型",
    ("*", "No SMPL model selected"): "尚未选中 SMPL 人体模型",
    ("*", "Target Height [m]"): "目标身高 [米]",
    ("*", "Target Weight [kg]"): "目标体重 [千克]",
    ("*", "Measurements To Shape"): "根据身高体重生成体型",
    ("*", "Calculate and set shape parameters for specified measurements"): "根据输入的身高和体重估算并设置 SMPL 体型参数",
    ("*", "Random"): "随机体型",
    ("*", "Sets all shape blend shape keys to a random value"): "随机生成一组人体体型参数",
    ("*", "Reset"): "重置",
    ("*", "Resets all blend shape keys for shape"): "将人体体型恢复为默认值",
    ("*", "Snap To Ground Plane"): "脚底贴地",
    ("*", "Snaps mesh to the XY ground plane"): "将人体脚底移动到 XY 地面",
    ("*", "Update Joint Locations"): "更新关节位置",
    ("*", "Update joint locations after shape changes"): "体型变化后重新计算骨骼关节位置",
    ("*", "Random Face Expression"): "随机面部表情",
    ("*", "Sets all face expression blend shape keys to a random value"): "随机生成一组面部表情参数",
    ("*", "Resets all blend shape keys for face expression"): "将面部表情恢复为默认值",

    # Pose controls.
    ("*", "Pose"): "姿态",
    ("*", "Corrective Pose Shapes"): "启用姿态修正",
    ("*", "Enable/disable corrective pose shapes of SMPL-X model"): "启用或关闭 SMPL-X 关节弯曲外形修正",
    ("*", "Update Pose Shapes"): "更新姿态修正",
    ("*", "Sets and updates corrective poseshapes for current pose"): "根据当前骨骼姿态更新关节外形修正",
    ("*", "Resets corrective poseshapes for current pose"): "清除当前姿态的关节外形修正",
    ("*", "Hand Pose:"): "手部姿态：",
    ("*", "SMPL-X hand pose"): "SMPL-X 手部姿态",
    ("*", "Relaxed"): "自然放松",
    ("*", "Flat"): "手掌伸平",
    ("*", "Set selected hand pose"): "应用所选手部姿态",
    ("*", "Write Pose To Console"): "将姿态输出到控制台",
    ("*", "Writes SMPL-X flat hand pose thetas to console window"): "将当前 SMPL-X 姿态参数输出到控制台",
    ("*", "Reset Pose"): "姿态归零",
    ("*", "Resets pose to default zero pose"): "将全部骨骼恢复到默认零姿态",
    ("*", "Load Pose"): "加载姿态文件",
    ("*", "Load relaxed-hand model pose from file"): "从文件载入带自然手势的人体姿态",
    ("*", "Update shape parameters"): "同时更新体型参数",
    ("*", "Update shape parameters using the beta shape information in the loaded file"): "使用载入文件中的 beta 信息更新体型参数",

    # Animation and export (kept available for research users).
    ("*", "Animation"): "动画",
    ("*", "Add Animation"): "载入人体动画",
    ("*", "Load AMASS/SMPL-X animation and create animated SMPL-X/SMPL+H body"): "载入 AMASS/SMPL-X 动画并生成带动画的人体",
    ("*", "Format"): "格式",
    ("*", "Body rest position"): "人体静止姿态",
    ("*", "Hand pose reference"): "手部参考姿态",
    ("*", "Use keyframed corrective pose weights"): "记录逐帧姿态修正权重",
    ("*", "Target framerate [fps]"): "目标帧率 [帧/秒]",
    ("*", "Export"): "导出",
    ("*", "Export Alembic ABC"): "导出 Alembic（ABC）",
    ("*", "Export as Alembic geometry cache"): "导出为 Alembic 几何缓存",
    ("*", "Export FBX"): "导出 FBX",
    ("*", "Export skinned mesh in FBX format"): "将蒙皮人体导出为 FBX 格式",
    ("*", "Animation Only"): "仅导出动画",
    ("*", "Export only the animation (armature) without the mesh"): "仅导出骨骼动画，不包含人体网格",
    ("*", "Export Shape"): "导出体型参数",
    ("*", "Export shape beta values in NPZ format"): "将体型 beta 参数导出为 NPZ 文件",
}


# Blender resolves operator ``bl_label`` strings in a separate context.  Mirror
# all doctor-facing terms there so explicit operator buttons are translated too.
for _key, _translated in tuple(_ZH_HANS.items()):
    if _key[0] == "*":
        _ZH_HANS.setdefault(("Operator", _key[1]), _translated)


TRANSLATIONS = {
    "zh_HANS": _ZH_HANS,
    # Blender 3.6 used this locale identifier on some installations.
    "zh_CN": _ZH_HANS,
}


def enable_blender_chinese(save_preferences=False):
    """Enable Simplified Chinese labels without translating data-block names."""
    view = bpy.context.preferences.view
    try:
        view.language = "zh_HANS"
    except TypeError:
        view.language = "zh_CN"
    view.use_translate_interface = True
    view.use_translate_tooltips = True
    view.use_translate_new_dataname = False
    if save_preferences:
        bpy.ops.wm.save_userpref()


def register_translations():
    try:
        bpy.app.translations.unregister(TRANSLATION_DOMAIN)
    except (ValueError, RuntimeError):
        pass
    bpy.app.translations.register(TRANSLATION_DOMAIN, TRANSLATIONS)


def unregister_translations():
    try:
        bpy.app.translations.unregister(TRANSLATION_DOMAIN)
    except (ValueError, RuntimeError):
        pass


def apply_to_running_session(save_preferences=False):
    """Hot-apply translations to an open Blender session without touching scene data."""
    register_translations()
    enable_blender_chinese(save_preferences=save_preferences)
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()


if __name__ == "__main__":
    apply_to_running_session(save_preferences=True)
