import os, time, unreal

# ---- config ----
LEVEL_PATH = "/Game/Levels/Playground"
FLOOR_SIZE_M = 100.0     # 100m x 100m
FLOOR_Z_CM   = 0.0
SUN_LABEL, SKY_LABEL   = "SunLight", "SkyLight"
ATM_LABEL, FOG_LABEL   = "SkyAtmosphere", "ExpHeightFog"
FLOOR_LABEL, CAM_LABEL = "PlaygroundFloor", "camera_0"
CAP_LABEL              = "AgentCapture2D"

# ---- shorthands ----
ELL = unreal.EditorLevelLibrary
EAL = unreal.EditorAssetLibrary
EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
ARH = unreal.AssetRegistryHelpers
RL  = unreal.RenderingLibrary
ML  = unreal.MathLibrary

log = lambda m: unreal.log(f"[init_editor] {m}")

# ---- diagnostics (concise) ----
def _dump_levels(tag: str):
    ar = ARH.get_asset_registry(); 
    try: ar.wait_for_completion()
    except Exception: pass
    ads = ar.get_assets_by_path("/Game", recursive=True) or []
    lvls = sorted(str(getattr(a, "package_name", "")) for a in ads
                  if str(getattr(getattr(a, "asset_class_path", ""), "asset_name", "")) == "World")
    log(f"{tag} levels: {len(lvls)}"); [log(f"  {x}") for x in lvls]

# ---- helpers ----
def _ensure_level(p: str):
    if not EAL.does_asset_exist(p):
        if not ELL.new_level(p): raise RuntimeError(f"new_level failed: {p}")
    if not ELL.load_level(p):    raise RuntimeError(f"load_level failed: {p}")

def _find_by_label(label, cls=None):
    for a in ELL.get_all_level_actors():
        if a.get_actor_label() == label and (cls is None or isinstance(a, cls)):
            return a
    return None

def _ensure_actor(cls, label, loc=None, rot=None):
    a = _find_by_label(label, cls)
    if a: return a
    a = EAS.spawn_actor_from_class(cls, loc or unreal.Vector(0,0,300), rot or unreal.Rotator())
    a.set_actor_label(label); return a

# ---- scene setup ----
def ensure_environment():
    _ensure_level(LEVEL_PATH)

    sun = _ensure_actor(unreal.DirectionalLight, SUN_LABEL, unreal.Vector(0,0,800), unreal.Rotator(-35,-45,0))
    sc  = sun.get_component_by_class(unreal.DirectionalLightComponent)
    if sc:
        sc.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
        sc.set_editor_property("intensity", 50.0)
        sc.set_editor_property("cast_shadows", True)

    sky = _ensure_actor(unreal.SkyLight, SKY_LABEL)
    skc = sky.get_component_by_class(unreal.SkyLightComponent)
    if skc:
        skc.set_editor_property("mobility", unreal.ComponentMobility.STATIONARY)
        skc.set_editor_property("real_time_capture", True)

    _ensure_actor(unreal.SkyAtmosphere,        ATM_LABEL)
    _ensure_actor(unreal.ExponentialHeightFog, FOG_LABEL)

    floor = _find_by_label(FLOOR_LABEL, unreal.StaticMeshActor)
    if not floor:
        floor = _ensure_actor(unreal.StaticMeshActor, FLOOR_LABEL, unreal.Vector(0,0,FLOOR_Z_CM))
        smc = floor.get_component_by_class(unreal.StaticMeshComponent)
        smc.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Plane"))
        floor.set_actor_scale3d(unreal.Vector(FLOOR_SIZE_M, FLOOR_SIZE_M, 1.0))
        floor.set_actor_location(unreal.Vector(0,0,FLOOR_Z_CM), False, False)

    ELL.save_current_level()

def ensure_camera_0():
    cam = _ensure_actor(unreal.CineCameraActor, CAM_LABEL, unreal.Vector(-2000,-2000,600))
    cam.set_actor_rotation(ML.find_look_at_rotation(cam.get_actor_location(), unreal.Vector(0,0,FLOOR_Z_CM)), False)
    cine = getattr(cam, "cine_camera_component", None) or getattr(cam, "get_cine_camera_component", lambda:None)()
    if cine:
        cine.set_editor_property("current_focal_length", 35.0)
        cine.set_editor_property("current_aperture", 2.8)
    return cam

def ensure_capture2d(width=1280, height=720):
    cap = _find_by_label(CAP_LABEL, unreal.SceneCapture2D)
    if not cap:
        cap = EAS.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(0,0,200), unreal.Rotator())
        cap.set_actor_label(CAP_LABEL)

    comp  = cap.capture_component2d
    world = ELL.get_editor_world()

    rt = comp.texture_target
    if (not rt) or rt.size_x != width or rt.size_y != height:
        rt = RL.create_render_target2d(world, width, height,
                unreal.TextureRenderTargetFormat.RTF_RGBA8, unreal.LinearColor(0,0,0,1), False)
        comp.texture_target = rt

    # Final Color (LDR)
    comp.capture_source = unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR

    # Disable auto exposure on the capture (UE5.6 naming)
    pps = comp.post_process_settings
    pps.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)  # no separate override flag

    # Clamp exposure so adaptation is off (Min == Max)
    for flag in ("override_auto_exposure_min_brightness", "override_auto_exposure_max_brightness"):
        pps.set_editor_property(flag, True)
    pps.set_editor_property("auto_exposure_min_brightness", 1.0)
    pps.set_editor_property("auto_exposure_max_brightness", 1.0)

    comp.post_process_blend_weight = 1.0

    return cap, comp, rt

# ---- export ----
def _ensure_dir(path:str): os.makedirs(os.path.dirname(path), exist_ok=True)

def screenshot_from_camera0(path, width=1280, height=720):
    import os
    cam = ensure_camera_0()
    cap, comp, rt = ensure_capture2d(width, height)

    comp.capture_every_frame = True
    comp.always_persist_rendering_state = True


    cap.set_actor_location(cam.get_actor_location(), False, False)
    cap.set_actor_rotation(cam.get_actor_rotation(), False)

    frames, handle = {"n": 0}, {"h": None}
    def _tick(dt):
        comp.capture_scene()
        frames["n"] += 1
        if frames["n"] >= 3:
            unreal.unregister_slate_post_tick_callback(handle["h"])
            world = ELL.get_editor_world()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            RL.export_render_target(world, rt, os.path.dirname(path), os.path.basename(path))
            log(f"wrote {path}")

    handle["h"] = unreal.register_slate_post_tick_callback(_tick)
    return path

# Workspace helpers
def get_workspace_dir() -> str:
    # 1) env var WORK_SPACE (highest priority)
    ws = os.environ.get("WORK_SPACE")
    if not ws or not ws.strip():
        # 2) fallback to <Project>/Saved/WORK_SPACE
        ws = os.path.join(unreal.Paths.project_saved_dir(), "WORK_SPACE")
    ws = os.path.normpath(ws)
    os.makedirs(ws, exist_ok=True)
    unreal.log(f"[init_editor] WORK_SPACE = {ws}")
    return ws

def make_shot_path(name: str = "initial", ext: str = ".png") -> str:
    ts = time.strftime("%Y%m%d_%H%M%S")
    return os.path.join(get_workspace_dir(), f"{name}_{ts}{ext}")

# ---- tiny delayed call (non-blocking; uses Slate tick) ----
def call_after(seconds: float, func, *args, **kwargs):
    left = {"t": float(seconds)}; handle = {"h": None}
    def _tick(dt: float):
        left["t"] -= float(dt)
        if left["t"] <= 0.0:
            unreal.unregister_slate_post_tick_callback(handle["h"])
            func(*args, **kwargs)
    handle["h"] = unreal.register_slate_post_tick_callback(_tick)

# ---- entry ----
def main():
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)  # keep editor alive
    log(f"Engine {unreal.SystemLibrary.get_engine_version()}")
    _dump_levels("PRE")
    ensure_environment()
    ensure_camera_0()
    _dump_levels("POST")
    # example (uncomment): delay then screenshot
    # call_after(0.3, screenshot_from_camera0, r"E:\UE\AITest_56\Content\Python\initial.png", 1280, 720)
    log("Ready...")

if __name__ == "__main__":
    main()
    # call_after(3, screenshot_from_camera0, '/data/koe/initial.png', 1280, 720)  # allow exit after a while