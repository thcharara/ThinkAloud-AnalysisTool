"""
Flask app for the Inductive Think-Aloud coding tool.

Serves the highlight-based coding workspace (``/code-v2``) where a researcher:
- selects raw transcript text to create micro units (turns) and meso units (episodes),
- applies three-tier codes (A: Operations, B: Content, C: Strategy) + step tags,
- sees Distance-to-Truth scored against optional ground truth,
- exports feature-by-scene matrices and a zipped JSONL snapshot.

All coding is persisted via JSONLExporter to the configured exports directory
(corpus_enriched.jsonl, episodes.jsonl, structured_json/, CHANGELOG.jsonl).
"""

import io
import zipfile
from datetime import datetime, timezone

from flask import Flask, render_template, jsonify, request, send_file
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.inductive_ta.distance_calculator import DistanceCalculator  # noqa: E402
from src.inductive_ta.jsonl_exporter import export_to_csv_matrices  # noqa: E402
from src.inductive_ta.models import Turn, Episode  # noqa: E402

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Global constants
PROJECT_ROOT = project_root


# ============================================================================
# Home: Project Validation
# ============================================================================

@app.route('/')
def index():
    """
    Home page with project validation.

    Blocks if validation fails; shows list of participants if passes.
    """
    # Run validation
    validation = app.config['loader'].validate_all()

    if not validation.is_valid():
        # Show blocking validation errors
        return render_template(
            'framework/validation.html',
            validation=validation
        )

    # Load participant list
    participant_ids = app.config['turn_parser'].get_participant_ids()

    # Load codebook for reference
    codebook = app.config['loader'].load_codebook()

    return render_template(
        'framework/index.html',
        participants=participant_ids,
        codebook=codebook
    )


# ============================================================================
# Coding Workspace (text-highlighting based UI)
# ============================================================================

@app.route('/code-v2/<participant_id>/<int:scene>')
def coder_v2(participant_id: str, scene: int):
    """
    Coding interface with text highlighting for unit creation.

    Features:
    - Raw transcript display with text selection
    - Create micro/meso units by highlighting
    - Clear operational definitions for all codes
    - Workflow-driven coding process
    """
    # Validate participant_id against the known participant list. This guards the
    # transcript path interpolation below and yields a clean 404 for unknown ids.
    if participant_id not in app.config["turn_parser"].get_participant_ids():
        return f"Unknown participant: {participant_id}", 404

    # Load scene data
    all_scenes = app.config["turn_parser"].parse_participant(participant_id)
    scene_data = next((s for s in all_scenes if s.scene == scene), None)
    if not scene_data:
        return f"Scene {scene} not found for {participant_id}", 404

    # Get raw transcript text for this scene
    transcript_path = app.config["turn_parser"].transcripts_dir / f"{participant_id}.txt"
    raw = transcript_path.read_text(encoding='utf-8', errors='replace')

    # Extract scene-specific text
    chunks = {}
    text = raw
    matches = list(app.config["turn_parser"].scene_regex.finditer(text))
    for idx, m in enumerate(matches):
        num = int(m.group('num'))
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        chunks[num] = text[start:end]

    scene_text = chunks.get(scene, '')

    # Load existing codes from JSONL if available
    existing_turns = app.config["exporter"].load_turns_for_participant_scene(participant_id, scene)
    existing_episodes = app.config["exporter"].load_episodes_for_participant_scene(participant_id, scene)

    # Load codebook and ground truth
    codebook = app.config["loader"].load_codebook()
    scene_key = app.config["loader"].get_scene_key(scene)

    # Get all participants for navigator
    all_participants = app.config["turn_parser"].get_participant_ids()

    # Prepare data for template
    turns_data = [turn.model_dump() for turn in existing_turns] if existing_turns else []
    episodes_data = [episode.model_dump() for episode in existing_episodes] if existing_episodes else []

    # Create a scene_data object with raw_transcript
    from types import SimpleNamespace
    scene_display_data = SimpleNamespace(
        participant_id=participant_id,
        scene=scene,
        raw_transcript=scene_text,
        Correct=scene_data.Correct if hasattr(scene_data, 'Correct') else None,
        TimeSeconds=scene_data.TimeSeconds if hasattr(scene_data, 'TimeSeconds') else None,
        NumGuesses=scene_data.NumGuesses if hasattr(scene_data, 'NumGuesses') else None
    )

    return render_template(
        'framework/coder_v2.html',
        participant_id=participant_id,
        scene=scene,
        scene_data=scene_display_data,
        scene_key=scene_key,
        codebook=codebook,
        all_participants=all_participants,
        turns_json=turns_data,
        episodes_json=episodes_data
    )


# ============================================================================
# API: Save Coding
# ============================================================================

@app.post('/api/save-coding')
def api_save_coding():
    """
    Save coding data from the workspace.

    Accepts both micro units (turns) and meso units (episodes).
    """
    data = request.get_json()

    participant_id = data['participant_id']
    scene = data['scene']
    micro_units = data.get('micro_units', [])
    meso_units = data.get('meso_units', [])

    # Convert micro units to Turn objects and export
    turns = []
    for unit_data in micro_units:
        # Ensure char_start and char_end have default values
        if unit_data.get('char_start') is None:
            unit_data['char_start'] = 0
        if unit_data.get('char_end') is None:
            unit_data['char_end'] = len(unit_data.get('raw_text', ''))
        turn = Turn(**unit_data)
        turns.append(turn)

    # Convert meso units to Episode objects
    episodes = []
    for unit_data in meso_units:
        # Ensure turn_span_start and turn_span_end have default values
        if unit_data.get('turn_span_start') is None:
            unit_data['turn_span_start'] = 0
        if unit_data.get('turn_span_end') is None:
            unit_data['turn_span_end'] = 0

        # Set default episode_type if missing
        if 'episode_type' not in unit_data:
            unit_data['episode_type'] = 'hypothesis_episode'

        # Ensure chunk fields have defaults
        if 'chunk_type' not in unit_data:
            unit_data['chunk_type'] = None
        if 'chunk_description' not in unit_data:
            unit_data['chunk_description'] = ''

        episode = Episode(**unit_data)
        episodes.append(episode)

    # Validate all codes against the loaded codebook before persisting. This is
    # codebook-driven (not tied to a fixed enum), so it works for any custom
    # codebook, and we reject up front so no partial/invalid data is written.
    codebook = app.config["loader"].load_codebook()
    valid_a = set(codebook.get_all_operation_codes())
    valid_b = set(codebook.get_all_b_codes())
    valid_step = set(codebook.get_all_step_tags())
    valid_c = set(codebook.get_all_strategy_codes())

    invalid = []
    for t in turns:
        if t.A_operation and t.A_operation not in valid_a:
            invalid.append(f"A_operation '{t.A_operation}'")
        for b in (t.B_content or []):
            if b not in valid_b:
                invalid.append(f"B_content '{b}'")
        if t.step_tag and t.step_tag not in valid_step:
            invalid.append(f"step_tag '{t.step_tag}'")
    for e in episodes:
        for s in (e.StrategyCodes or []):
            if s not in valid_c:
                invalid.append(f"StrategyCode '{s}'")

    if invalid:
        return jsonify({
            'error': 'One or more codes are not defined in the codebook',
            'invalid': sorted(set(invalid)),
        }), 400

    # Export using the participant_scene method (handles JSONL updates correctly)
    if turns or episodes:
        app.config["exporter"].export_participant_scene(participant_id, scene, turns, episodes)

        if turns:
            app.config["exporter"].log_change(participant_id, scene, action_type='bulk_save_turns',
                              after={'count': len(turns)})
            # Also export structured JSON with labels
            app.config["exporter"].export_structured_json(participant_id, scene, turns)

        if episodes:
            app.config["exporter"].log_change(participant_id, scene, action_type='bulk_save_episodes',
                              after={'count': len(episodes)})

    return jsonify({'success': True, 'turns_saved': len(turns), 'episodes_saved': len(episodes)})


# ============================================================================
# API: Distance-to-Truth
# ============================================================================

@app.post('/api/calculate-distance')
def api_calculate_distance():
    """Score an episode's FeatureBundle against the scene's ground truth.

    Authoritative scoring lives in distance_calculator.py so it stays testable
    and reusable for batch re-scoring; the UI calls this rather than duplicating
    the algorithm in JavaScript.
    """
    data = request.get_json() or {}
    scene = data['scene']
    feature_bundle = data.get('FeatureBundle', [])

    scene_key = app.config["loader"].get_scene_key(scene)
    if not scene_key:
        return jsonify({'error': 'No ground truth for this scene'}), 404

    temp_episode = Episode(
        episode_id="temp", participant_id="temp", scene=scene,
        episode_index=0, turn_span_start=0, turn_span_end=0,
        FeatureBundle=feature_bundle,
    )
    calculator = DistanceCalculator(scene_key)
    return jsonify({
        'distance': calculator.calculate(temp_episode).value,
        'explanation': calculator.explain(temp_episode),
    })


# ============================================================================
# API: Export Helpers
# ============================================================================

@app.post('/api/export/matrices')
def api_export_matrices():
    """Generate matrix CSVs (feature attention, evidence policy)."""
    turns = app.config["exporter"].load_turns()
    episodes = app.config["exporter"].load_episodes()
    export_to_csv_matrices(turns, episodes, app.config["exporter"].exports_dir)
    timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    return jsonify({'success': True, 'timestamp': timestamp})


@app.get('/api/export/snapshot')
def api_export_snapshot():
    """Download a zip snapshot of current JSONL exports."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename in ['corpus_enriched.jsonl', 'episodes.jsonl', 'CHANGELOG.jsonl']:
            path = app.config["exporter"].exports_dir / filename
            if path.exists():
                zf.write(path, arcname=filename)

    buffer.seek(0)
    download_name = f"thinkaloud_snapshot_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.zip"
    return send_file(buffer, mimetype='application/zip', as_attachment=True, download_name=download_name)


# ============================================================================
# Task images (one reference image per scene)
# ============================================================================

@app.route('/task-image/<int:scene>')
def task_image(scene: int):
    """
    Serve task image for a given scene.
    Images are stored in task_images/ with names like "Scene 1 - at least one red.png"
    """
    task_images_dir = project_root / "task_images"

    # Map scene number to image filename
    scene_image_map = {
        1: "Scene 1 - at least one red.png",
        2: "Scene 2 - small blue cone.png",
        3: "Scene 3 - two tilted blue cones.png",
        4: "Scene 4 - stacked cones of different colors.png",
        5: "Scene 5 - more red than any color.png"
    }

    image_filename = scene_image_map.get(scene)
    if not image_filename:
        return jsonify({'error': 'Invalid scene number'}), 404

    image_path = task_images_dir / image_filename
    if not image_path.exists():
        return jsonify({'error': f'Image not found: {image_filename}'}), 404

    return send_file(image_path, mimetype='image/png')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Inductive Think-Aloud Framework UI')
    parser.add_argument('--config', type=str, default='config/config_demo.yaml',
                        help='Path to config file (default: config/config_demo.yaml for the demo; use config/config.yaml for your own research data)')
    parser.add_argument('--port', type=int, default=5002,
                        help='Port to run server on (default: 5002)')
    parser.add_argument('--debug', action='store_true', default=False,
                        help='Run in debug mode (default: False)')

    args = parser.parse_args()

    # Initialize loaders with specified config and store in app.config
    from src.inductive_ta.project_loader import ProjectLoader
    from src.inductive_ta.turn_parser import TurnParser
    from src.inductive_ta.jsonl_exporter import JSONLExporter

    app.config['loader'] = ProjectLoader(PROJECT_ROOT, config_path=args.config)
    app.config['turn_parser'] = TurnParser(PROJECT_ROOT, config_path=args.config)

    # Get exports_dir from config
    import yaml
    config_file = PROJECT_ROOT / args.config
    with open(config_file) as f:
        config = yaml.safe_load(f)
    exports_dir = PROJECT_ROOT / config['paths']['exports_dir']
    app.config['exporter'] = JSONLExporter(exports_dir)

    print(f"\n{'='*60}")
    print("Inductive Think-Aloud Framework UI")
    print(f"{'='*60}")
    print(f"Config file: {args.config}")
    print(f"Transcripts: {config['paths']['transcripts_dir']}")
    print(f"Exports: {config['paths']['exports_dir']}")
    print(f"Port: {args.port}")
    print(f"{'='*60}\n")
    print(f"Open your browser to: http://localhost:{args.port}")
    print("\nTip: Use --config config/config_demo.yaml for demo data")
    print(f"{'='*60}\n")

    app.run(debug=args.debug, port=args.port)
