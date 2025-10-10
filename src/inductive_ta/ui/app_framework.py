"""
Framework-compliant Flask app for Inductive Think-Aloud coding.

Implements:
- Tri-pane layout (Navigator | Transcript | Coding Sidebar)
- Turn-based coding (not word-selection)
- Three-tier codebook (A: Operations, B: Content, C: Strategy)
- Episode scaffolding with all required fields
- Ground truth integration with distance-to-truth
- JSONL exports (corpus_enriched.jsonl, episodes.jsonl)
- Audit trail (CHANGELOG.jsonl)
"""

import io
import zipfile
from datetime import datetime

from flask import Flask, render_template, jsonify, request, send_file
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.inductive_ta.project_loader import ProjectLoader
from src.inductive_ta.turn_parser import TurnParser
from src.inductive_ta.distance_calculator import DistanceCalculator
from src.inductive_ta.jsonl_exporter import JSONLExporter, export_to_csv_matrices
from src.inductive_ta.models import Turn, Episode, InlineSpan
from src.inductive_ta.analytics import suggest_turn_codes, compute_scene_statistics

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
# Coder Workspace (Tri-pane layout)
# ============================================================================

@app.route('/code/<participant_id>/<int:scene>')
def coder_workspace(participant_id: str, scene: int):
    """
    Main coding interface with tri-pane layout.

    Left: Navigator (participants/scenes)
    Center: Transcript view (turns with episode bands)
    Right: Coding sidebar (Tier A/B/C, step-tags, episode editor)
    """
    # Load participant's scene data
    scene_data = turn_parser.load_participant_scene(participant_id, scene)
    if not scene_data:
        return f"Scene {scene} not found for {participant_id}", 404

    # Load existing codes from JSONL if available
    existing_turns = exporter.load_turns_for_participant_scene(participant_id, scene)
    existing_episodes = exporter.load_episodes_for_participant_scene(participant_id, scene)

    # Merge existing codes into parsed turns
    if existing_turns:
        turn_dict = {t.turn_index: t for t in existing_turns}
        for turn in scene_data.turns:
            if turn.turn_index in turn_dict:
                existing = turn_dict[turn.turn_index]
                turn.A_operation = existing.A_operation
                turn.B_content = existing.B_content
                turn.step_tag = existing.step_tag
                turn.notes = existing.notes

    # Add episodes to scene_data
    scene_data.episodes = existing_episodes

    # Load codebook and ground truth
    codebook = loader.load_codebook()
    scene_key = loader.get_scene_key(scene)

    # Get all participants for navigator
    all_participants = turn_parser.get_participant_ids()

    # Convert turns and episodes to dicts for JSON serialization
    turns_data = [turn.model_dump() for turn in scene_data.turns]
    episodes_data = [episode.model_dump() for episode in scene_data.episodes]

    return render_template(
        'framework/coder.html',
        participant_id=participant_id,
        scene=scene,
        scene_data=scene_data,
        scene_key=scene_key,
        codebook=codebook,
        all_participants=all_participants,
        turns_json=turns_data,
        episodes_json=episodes_data
    )


# ============================================================================
# Inline Coding Workspace (no auto turns)
# ============================================================================

@app.route('/inline/<participant_id>/<int:scene>')
def inline_coder(participant_id: str, scene: int):
    """Inline span coding view: renders raw scene text and allows span-level coding."""
    # Load scene raw text using TurnParser split (but do not create turn objects)
    all_scenes = turn_parser.parse_participant(participant_id)
    scene_data = next((s for s in all_scenes if s.scene == scene), None)
    if not scene_data:
        return f"Scene {scene} not found for {participant_id}", 404

    # Reconstruct scene text by concatenating original lines in that scene
    # turn_parser._split_into_scenes already preserved raw lines; here we rebuild from transcript file
    transcript_path = turn_parser.transcripts_dir / f"{participant_id}.txt"
    raw = transcript_path.read_text(encoding='utf-8', errors='replace')
    # Compute scene chunks with the parser regex
    chunks = {}
    text = raw
    matches = list(turn_parser.scene_regex.finditer(text))
    for idx, m in enumerate(matches):
        num = int(m.group('num'))
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        chunks[num] = text[start:end]
    scene_text = chunks.get(scene, '')

    # Load existing spans for this scene
    spans = exporter.load_spans_for_participant_scene(participant_id, scene)

    codebook = loader.load_codebook()
    scene_key = loader.get_scene_key(scene)
    all_participants = turn_parser.get_participant_ids()

    return render_template(
        'framework/inline.html',
        participant_id=participant_id,
        scene=scene,
        scene_text=scene_text,
        spans_json=[s.model_dump() for s in spans],
        codebook=codebook,
        scene_key=scene_key,
        all_participants=all_participants,
    )


# ============================================================================
# API: Save Turn Codes
# ============================================================================

@app.post('/api/save-turn')
def api_save_turn():
    """
    Save codes for a single turn.

    Request JSON:
    {
        "participant_id": "P01",
        "scene": 1,
        "turn_index": 5,
        "A_operation": "HYPOTHESIZE",
        "B_content": ["COLOR_Blue", "SIZE_Small"],
        "step_tag": "STEP_HYP",
        "notes": ""
    }
    """
    data = request.get_json()

    participant_id = data['participant_id']
    scene = data['scene']
    turn_index = data['turn_index']

    # Load scene turns
    scene_data = turn_parser.load_participant_scene(participant_id, scene)
    if not scene_data:
        return jsonify({'error': 'Scene not found'}), 404

    # Find turn
    turn = next((t for t in scene_data.turns if t.turn_index == turn_index), None)
    if not turn:
        return jsonify({'error': 'Turn not found'}), 404

    # Log change for audit trail
    before = {
        'A_operation': turn.A_operation,
        'B_content': turn.B_content,
        'step_tag': turn.step_tag
    }

    # Update turn
    turn.A_operation = data.get('A_operation')
    turn.B_content = data.get('B_content', [])
    turn.step_tag = data.get('step_tag')
    turn.notes = data.get('notes', '')

    after = {
        'A_operation': turn.A_operation,
        'B_content': turn.B_content,
        'step_tag': turn.step_tag
    }

    # Export updated turns
    exporter.export_participant_scene(
        participant_id, scene,
        scene_data.turns,
        scene_data.episodes
    )

    # Log to changelog
    exporter.log_change(
        participant_id, scene,
        action_type='update_turn',
        before=before,
        after=after,
        notes=f"Turn {turn_index}"
    )

    return jsonify({'success': True})


# ============================================================================
# API: Create/Update Episode
# ============================================================================

@app.post('/api/save-episode')
def api_save_episode():
    """
    Create or update an episode.

    Request JSON:
    {
        "participant_id": "P01",
        "scene": 1,
        "episode_id": "P01_S1_EP0",  # or null for new episode
        "episode_index": 0,
        "turn_span_start": 10,
        "turn_span_end": 25,
        "HypothesisVerbatim": "I think it's the small blue cone",
        "FeatureBundle": ["color=blue", "size=small"],
        "EvidenceCited": "PositiveCases",
        "Confidence": "Hedged",
        "Outcome": "accepted",
        "StrategyCodes": ["EvidencePolicy_Contrastive", "Complexity_Conjunctive"],
        "DistanceToTruth": "ExactMatch",
        "Notes": ""
    }
    """
    data = request.get_json()

    participant_id = data['participant_id']
    scene = data['scene']
    episode_id = data.get('episode_id')

    # Load existing episodes
    episodes = exporter.load_episodes_for_participant_scene(participant_id, scene)

    # Find or create episode
    if episode_id:
        # Update existing
        episode = next((e for e in episodes if e.episode_id == episode_id), None)
        if not episode:
            return jsonify({'error': 'Episode not found'}), 404
    else:
        # Create new
        episode_index = len(episodes)
        episode_id = f"{participant_id}_S{scene}_EP{episode_index}"
        episode = Episode(
            episode_id=episode_id,
            participant_id=participant_id,
            scene=scene,
            episode_index=episode_index,
            turn_span_start=data['turn_span_start'],
            turn_span_end=data['turn_span_end']
        )
        episodes.append(episode)

    # Update fields
    episode.HypothesisVerbatim = data.get('HypothesisVerbatim', '')
    episode.FeatureBundle = data.get('FeatureBundle', [])
    episode.EvidenceCited = data.get('EvidenceCited')
    episode.Confidence = data.get('Confidence')
    episode.Outcome = data.get('Outcome')
    episode.StrategyCodes = data.get('StrategyCodes', [])
    episode.DistanceToTruth = data.get('DistanceToTruth')
    episode.Notes = data.get('Notes', '')

    # Load turns for export
    turns = exporter.load_turns_for_participant_scene(participant_id, scene)
    if not turns:
        # Use parsed turns
        scene_data = turn_parser.load_participant_scene(participant_id, scene)
        turns = scene_data.turns if scene_data else []

    # Export
    exporter.export_participant_scene(participant_id, scene, turns, episodes)

    # Log to changelog
    exporter.log_change(
        participant_id, scene,
        action_type='save_episode',
        after={'episode_id': episode_id},
        notes=f"Episode {episode_id}"
    )

    return jsonify({'success': True, 'episode_id': episode_id})


# ============================================================================
# API: Calculate Distance-to-Truth
# ============================================================================

@app.post('/api/calculate-distance')
def api_calculate_distance():
    """
    Calculate distance-to-truth for an episode.

    Request JSON:
    {
        "scene": 1,
        "FeatureBundle": ["color=blue", "size=small"]
    }

    Response JSON:
    {
        "distance": "ExactMatch",
        "explanation": "✅ Exact match: all required features present"
    }
    """
    data = request.get_json()
    scene = data['scene']
    feature_bundle = data.get('FeatureBundle', [])

    # Load ground truth
    scene_key = loader.get_scene_key(scene)
    if not scene_key:
        return jsonify({'error': 'Scene key not found'}), 404

    # Create temporary episode for calculation
    temp_episode = Episode(
        episode_id="temp",
        participant_id="temp",
        scene=scene,
        episode_index=0,
        turn_span_start=0,
        turn_span_end=0,
        FeatureBundle=feature_bundle
    )

    # Calculate
    calculator = DistanceCalculator(scene_key)
    distance = calculator.calculate(temp_episode)
    explanation = calculator.explain(temp_episode)

    return jsonify({
        'distance': distance.value,
        'explanation': explanation
    })


# ============================================================================
# API: Get Codebook Reference
# ============================================================================

@app.get('/api/codebook')
def api_codebook():
    """
    Get full codebook with definitions.

    Response includes:
    - Tier A operations with descriptions
    - Tier B content categories (B1-B6) with descriptions
    - Tier C strategy codes with descriptions
    - Step-tags with descriptions
    """
    codebook = loader.load_codebook()

    return jsonify({
        'meta': codebook.meta,
        'tier_a': codebook.get_tier_a_operations(),
        'tier_b': codebook.get_tier_b_content(),
        'tier_c': codebook.get_tier_c_strategy(),
        'step_tags': codebook.step_tags
    })


# ============================================================================
# API: Delete Episode
# ============================================================================

@app.delete('/api/delete-episode/<episode_id>')
def api_delete_episode(episode_id: str):
    """
    Delete an episode.

    Args:
        episode_id: e.g., "P01_S1_EP2"
    """
    # Parse episode_id to get participant and scene
    parts = episode_id.split('_')
    if len(parts) < 3:
        return jsonify({'error': 'Invalid episode_id format'}), 400

    participant_id = parts[0]
    scene = int(parts[1][1:])  # Remove 'S' prefix

    # Load episodes
    episodes = exporter.load_episodes_for_participant_scene(participant_id, scene)

    # Find and remove
    episodes = [e for e in episodes if e.episode_id != episode_id]

    # Load turns
    turns = exporter.load_turns_for_participant_scene(participant_id, scene)

    # Export
    exporter.export_participant_scene(participant_id, scene, turns, episodes)

    # Log
    exporter.log_change(
        participant_id, scene,
        action_type='delete_episode',
        before={'episode_id': episode_id},
        notes=f"Deleted {episode_id}"
    )

    return jsonify({'success': True})


# ============================================================================
# API: Suggestions & Scene Analytics
# ============================================================================


@app.post('/api/suggest')
def api_suggest():
    """Return heuristic suggestions for a single turn."""
    data = request.get_json() or {}
    text = data.get('text', '')
    tag = data.get('tag')

    if not text.strip():
        return jsonify({'suggestions': {}})

    suggestions = suggest_turn_codes(text, tag)
    return jsonify({'suggestions': suggestions})


@app.get('/api/scene-stats')
def api_scene_stats():
    """Aggregate statistics for a participant × scene."""
    participant_id = request.args.get('participant_id')
    scene = request.args.get('scene', type=int)

    if not participant_id or scene is None:
        return jsonify({'error': 'participant_id and scene are required'}), 400

    turns = exporter.load_turns_for_participant_scene(participant_id, scene)
    episodes = exporter.load_episodes_for_participant_scene(participant_id, scene)

    # If no saved annotations yet, fall back to parsed turns for counts
    if not turns:
        scene_data = turn_parser.load_participant_scene(participant_id, scene)
        turns = scene_data.turns if scene_data else []
        episodes = scene_data.episodes if scene_data else []

    stats = compute_scene_statistics(turns, episodes)
    return jsonify(stats)


# ============================================================================
# API: Export Helpers
# ============================================================================


@app.post('/api/export/matrices')
def api_export_matrices():
    """Generate matrix CSVs (feature attention, evidence policy)."""
    turns = exporter.load_turns()
    episodes = exporter.load_episodes()
    export_to_csv_matrices(turns, episodes, exporter.exports_dir)
    timestamp = datetime.utcnow().isoformat() + 'Z'
    return jsonify({'success': True, 'timestamp': timestamp})


@app.get('/api/export/snapshot')
def api_export_snapshot():
    """Download a zip snapshot of current JSONL exports."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename in ['corpus_enriched.jsonl', 'episodes.jsonl', 'CHANGELOG.jsonl']:
            path = exporter.exports_dir / filename
            if path.exists():
                zf.write(path, arcname=filename)

    buffer.seek(0)
    download_name = f"thinkaloud_snapshot_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.zip"
    return send_file(buffer, mimetype='application/zip', as_attachment=True, download_name=download_name)


# ============================================================================
# API: Inline span CRUD
# ============================================================================


@app.post('/api/spans/add')
def api_spans_add():
    data = request.get_json() or {}
    required = ['participant_id', 'scene', 'start', 'end', 'text']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400

    participant_id = data['participant_id']
    scene = int(data['scene'])
    start = int(data['start'])
    end = int(data['end'])
    text = data['text']

    span_id = f"{participant_id}_S{scene}_SP{start}"
    span = InlineSpan(
        span_id=span_id,
        participant_id=participant_id,
        scene=scene,
        start=start,
        end=end,
        text=text,
        A_operation=data.get('A_operation'),
        B_content=data.get('B_content', []),
        step_tag=data.get('step_tag'),
        notes=data.get('notes', ''),
    )
    exporter.add_span(span)
    exporter.log_change(participant_id, scene, action_type='add_span', after=span.model_dump(), notes='Inline span add')
    return jsonify({'success': True, 'span': span.model_dump()})


@app.delete('/api/spans/delete/<span_id>')
def api_spans_delete(span_id: str):
    # Best-effort: try to parse participant and scene for logging
    try:
        parts = span_id.split('_')
        participant_id = parts[0]
        scene = int(parts[1][1:])
    except Exception:
        participant_id, scene = 'NA', 0
    exporter.delete_span(span_id)
    exporter.log_change(participant_id, scene, action_type='delete_span', before={'span_id': span_id})
    return jsonify({'success': True})


@app.get('/api/spans/list')
def api_spans_list():
    participant_id = request.args.get('participant_id')
    scene = request.args.get('scene', type=int)
    if not participant_id or scene is None:
        return jsonify({'error': 'participant_id and scene are required'}), 400
    spans = exporter.load_spans_for_participant_scene(participant_id, scene)
    return jsonify({'spans': [s.model_dump() for s in spans]})


# ============================================================================
# V2 Coder: Text-Highlighting Based UI
# ============================================================================

@app.route('/code-v2/<participant_id>/<int:scene>')
def coder_v2(participant_id: str, scene: int):
    """
    V2 coding interface with text highlighting for unit creation.

    Features:
    - Raw transcript display with text selection
    - Create micro/meso/macro units by highlighting
    - Clear operational definitions for all codes
    - Visual when/how/why guidance
    - Workflow-driven coding process
    """
    # Load scene data
    all_scenes = turn_parser.parse_participant(participant_id)
    scene_data = next((s for s in all_scenes if s.scene == scene), None)
    if not scene_data:
        return f"Scene {scene} not found for {participant_id}", 404

    # Get raw transcript text for this scene
    transcript_path = turn_parser.transcripts_dir / f"{participant_id}.txt"
    raw = transcript_path.read_text(encoding='utf-8', errors='replace')

    # Extract scene-specific text
    chunks = {}
    text = raw
    matches = list(turn_parser.scene_regex.finditer(text))
    for idx, m in enumerate(matches):
        num = int(m.group('num'))
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        chunks[num] = text[start:end]

    scene_text = chunks.get(scene, '')

    # Load existing codes from JSONL if available
    existing_turns = exporter.load_turns_for_participant_scene(participant_id, scene)
    existing_episodes = exporter.load_episodes_for_participant_scene(participant_id, scene)

    # Load codebook and ground truth
    codebook = loader.load_codebook()
    scene_key = loader.get_scene_key(scene)

    # Get all participants for navigator
    all_participants = turn_parser.get_participant_ids()

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


@app.post('/api/save-coding')
def api_save_coding_v2():
    """
    Save coding data from V2 UI.

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

    # Export using the participant_scene method (handles JSONL updates correctly)
    if turns or episodes:
        exporter.export_participant_scene(participant_id, scene, turns, episodes)

        if turns:
            exporter.log_change(participant_id, scene, action_type='bulk_save_turns',
                              after={'count': len(turns)})
            # Also export structured JSON with labels
            exporter.export_structured_json(participant_id, scene, turns)

        if episodes:
            exporter.log_change(participant_id, scene, action_type='bulk_save_episodes',
                              after={'count': len(episodes)})

    return jsonify({'success': True, 'turns_saved': len(turns), 'episodes_saved': len(episodes)})


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
    parser.add_argument('--config', type=str, default='config/config.yaml',
                        help='Path to config file (default: config/config.yaml for your research data, use config/config_demo.yaml for demo)')
    parser.add_argument('--port', type=int, default=5002,
                        help='Port to run server on (default: 5002)')
    parser.add_argument('--debug', action='store_true', default=True,
                        help='Run in debug mode (default: True)')

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
    print(f"🚀 Inductive Think-Aloud Framework UI")
    print(f"{'='*60}")
    print(f"Config file: {args.config}")
    print(f"Transcripts: {config['paths']['transcripts_dir']}")
    print(f"Exports: {config['paths']['exports_dir']}")
    print(f"Port: {args.port}")
    print(f"{'='*60}\n")
    print(f"👉 Open your browser to: http://localhost:{args.port}")
    print(f"\n💡 Tip: Use --config config/config_demo.yaml for demo data")
    print(f"{'='*60}\n")

    app.run(debug=args.debug, port=args.port)
