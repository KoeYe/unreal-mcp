import os
import unreal

CAM_LABEL = "camera_0"
FLOOR_Z_CM   = 0.0

EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
ML  = unreal.MathLibrary
ELL = unreal.EditorLevelLibrary

def _ensure_actor(cls, label, loc=None, rot=None):
    a = _find_by_label(label, cls)
    if a: return a
    a = EAS.spawn_actor_from_class(cls, loc or unreal.Vector(0,0,300), rot or unreal.Rotator())
    a.set_actor_label(label); return a

def ensure_camera_0():
    cam = _ensure_actor(unreal.CineCameraActor, CAM_LABEL, unreal.Vector(-2000,-2000,600))
    cam.set_actor_rotation(ML.find_look_at_rotation(cam.get_actor_location(), unreal.Vector(0,0,FLOOR_Z_CM)), False)
    cine = getattr(cam, "cine_camera_component", None) or getattr(cam, "get_cine_camera_component", lambda:None)()
    if cine:
        cine.set_editor_property("current_focal_length", 35.0)
        cine.set_editor_property("current_aperture", 2.8)
    return cam

def _find_by_label(label, cls=None):
    for a in ELL.get_all_level_actors():
        if a.get_actor_label() == label and (cls is None or isinstance(a, cls)):
            return a
    return None

def get_workspace_dir() -> str:
    ws = os.environ.get("WORK_SPACE")
    os.makedirs(ws, exist_ok=True)
    return ws

def get_camera_view() -> str:
    """Get current view from camera_0 and save to workspace/images/currentimage.png"""
    
    # Find camera
    cam = ensure_camera_0()
    if not cam:
        raise RuntimeError(f"Camera '{CAM_LABEL}' not found")
    
    # Setup path
    images_dir = os.path.join(get_workspace_dir(), "images")
    os.makedirs(images_dir, exist_ok=True)
    
    # Remove old currentimage
    for ext in ['.png', '.jpg', '.jpeg']:
        old_path = os.path.join(images_dir, f"currentimage{ext}")
        if os.path.exists(old_path):
            os.remove(old_path)
    
    image_path = os.path.join(images_dir, "currentimage.png")
    
    # Capture from camera viewport
    unreal.AutomationLibrary.take_high_res_screenshot(1280, 720, image_path)
    return image_path

if __name__ == "__main__":
    try:
        path = get_camera_view()
        unreal.log(f"Camera view saved: {path}")
    except Exception as e:
        unreal.log_error(f"Failed: {e}")