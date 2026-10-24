"""Mock events, not the physics simulator or a real robot."""
from .autonomy import AutonomyBrain, Scene
from .episodic_memory import ExperienceMemory


def main() -> None:
    memory = ExperienceMemory("autonomy_demo.sqlite3")
    brain = AutonomyBrain(memory)
    scenes = [
        Scene(safe_area=True, floor_clear=True),
        Scene(safe_area=True, floor_clear=True,
              object_id="ball-01", pc_connected=True),
        Scene(safe_area=True, floor_clear=True,
              object_id="ball-01", object_label="ball"),
        Scene(safe_area=True, floor_clear=True,
              object_id="ball-01", object_label="ball"),
        Scene(safe_area=True, floor_clear=True, person_visible=True),
        Scene(safe_area=True, floor_clear=False, person_visible=True),
    ]
    for i, scene in enumerate(scenes, 1):
        plan = brain.choose(scene)
        print(f"Scene {i}: {plan.intention} / {plan.explanation} / pc={plan.request_pc_analysis}")
        if i == 3:
            brain.feedback("ball-01", plan.intention, reward=0.9)
    print("Known object:", memory.get("ball-01"))
    print("Experiences:", memory.experience_count())
    memory.close()


if __name__ == "__main__":
    main()
