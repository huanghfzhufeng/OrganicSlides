"""Tests for local SkillRuntime loading."""

from pathlib import Path

from skills.runtime import build_skill_prompt_packet, get_skill_runtime_packet, list_skill_runtimes


def test_get_skill_runtime_packet_loads_huashu_slides():
    packet = get_skill_runtime_packet("huashu-slides")

    assert packet["skill_id"] == "huashu-slides"
    assert packet["name"] == "huashu-slides"
    assert packet["default_collaboration_mode"] == "guided"
    assert packet["default_render_path"] == "path_a"
    assert len(packet["runtime_steps"]) >= 5
    assert "prompt-templates.md" in packet["reference_files"]
    assert Path(packet["skill_file"]).exists()
    assert Path(packet["scripts_dir"]).exists()


def test_build_skill_prompt_packet_contains_runtime_summary():
    packet = get_skill_runtime_packet("huashu-slides", "collaborative")
    prompt_packet = build_skill_prompt_packet(packet)

    assert "运行 Skill" in prompt_packet
    assert "协作模式" in prompt_packet
    assert "Path A" in prompt_packet
    assert "技能运行步骤" in prompt_packet


def test_list_skill_runtimes_discovers_local_skill():
    runtimes = list_skill_runtimes()

    assert any(item["skill_id"] == "huashu-slides" for item in runtimes)
