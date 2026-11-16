extends SceneTree
func _initialize():call_deferred("run")
func run():
 var audio=load("res://src/combat_audio.gd").new();root.add_child(audio)
 var failures:=[]
 audio.cue("late","flesh",Vector3.ZERO,2,301)
 if not audio.trace.is_empty():failures.append("late audio replay")
 audio.cue("contact","flesh",Vector3.ZERO,2)
 audio.cue("contact","flesh",Vector3.ZERO,2)
 if audio.trace.size()!=1:failures.append("duplicate event audio")
 for i in 1000:audio.cue("foot%d"%i,"foot",Vector3.ZERO,0)
 audio.cue("terminal","fall",Vector3.ZERO,3)
 if audio.trace[-1].id!="terminal":failures.append("death failed to preempt lower priority")
 if audio.voices.size()!=8 or audio.seen.size()>512:failures.append("unbounded pool")
 for voice in audio.voices:voice.stop()
 if audio.voices.any(func(v):return v.playing):failures.append("voices remain active")
 print(JSON.stringify({"audio_pool":audio.voices.size(),"dedup_entries":audio.seen.size(),"failures":failures,"method":"Dummy driver; no listening acceptance"}))
 audio.free();quit(0 if failures.is_empty() else 1)
