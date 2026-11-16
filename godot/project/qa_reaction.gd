extends SceneTree
func _initialize():call_deferred("run")
func run():
 var stage=load("res://src/landscape.gd").new();root.add_child(stage)
 # This unit probe intentionally does not call setup(); adopt its unparented
 # scene helpers so they are destroyed just as they are in a loaded scene.
 for property in stage.get_property_list():
  var helper=stage.get(property.name)
  if helper is Node and helper!=stage and helper.get_parent()==null:stage.add_child(helper)
 var model:=Node3D.new();var skeleton:=Skeleton3D.new();model.add_child(skeleton);root.add_child(model);skeleton.add_bone("Chest")
 var failures:=[]
 for i in 100:stage.additive_hit(model,.3)
 if skeleton.get_bone_pose_rotation(0).get_angle()>.0351:failures.append("additive reaction accumulated")
 stage.additive_hit(model,1.1)
 if not skeleton.get_bone_pose_rotation(0).is_equal_approx(Quaternion.IDENTITY):failures.append("expired reaction retained")
 stage.additive_hit(model,.3);var clip_pose:=Quaternion(Vector3.UP,.25);skeleton.set_bone_pose_rotation(0,clip_pose);stage.clear_additive_hit(model)
 if not skeleton.get_bone_pose_rotation(0).is_equal_approx(clip_pose):failures.append("new animation pose overwritten")
 print(JSON.stringify({"same_frame_reactions":100,"failures":failures,"method":"unkeyed spine lifecycle plus newly keyed pose; no device acceptance"}))
 model.free();stage.free();quit(0 if failures.is_empty() else 1)
