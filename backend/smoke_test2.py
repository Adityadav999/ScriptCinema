import sys, tempfile, os, shutil
sys.path.insert(0, '.')
from services.project_detector import detect_project
from services.project_runner import ProjectRunner
from services.video_producer import produce_terminal_video, produce_video

print("=== Import check ===")
print("produce_terminal_video:", produce_terminal_video)
print("produce_video:", produce_video)

print("\n=== Python script detection ===")
tmp = tempfile.mkdtemp()
with open(os.path.join(tmp, 'main.py'), 'w') as f:
    f.write('print("Hello ScriptCinema")\nfor i in range(5):\n    print(f"Line {i}")\n')
cfg = detect_project(tmp)
print(f"Detected: {cfg.project_type}, is_web={cfg.is_web}, port={cfg.port}")
runner = ProjectRunner(tmp, cfg)
lines = runner.run_and_capture(timeout=10)
print(f"Captured {len(lines)} lines: {lines}")
shutil.rmtree(tmp)

print("\n=== C++ detection ===")
tmp2 = tempfile.mkdtemp()
with open(os.path.join(tmp2, 'main.cpp'), 'w') as f:
    f.write('#include<iostream>\nint main(){std::cout<<"Hello C++"<<std::endl;return 0;}')
cfg2 = detect_project(tmp2)
print(f"Detected: {cfg2.project_type}, is_web={cfg2.is_web}")
print(f"Install cmd: {cfg2.install_cmd}")
print(f"Start cmd: {cfg2.start_cmd}")
shutil.rmtree(tmp2)

print("\nALL OK")
