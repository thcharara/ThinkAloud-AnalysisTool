from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict

from flask import Flask, abort, jsonify, render_template, request

from ..validation import build_context, validate_document
from ..hypothesis_tracker import (
    extract_hypotheses_from_text,
    get_hypothesis_graph,
)
from ..analytics import (
    calculate_code_usage_stats,
    detect_incomplete_cycles,
    validate_evidence_citations,
    detect_attribute_mismatches,
    calculate_inter_rater_agreement,
    generate_timeline_data,
    get_cross_scene_patterns,
)
from . import utils
from .utils import SceneSegment


UI_DIR = Path(__file__).resolve().parent


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=str(UI_DIR / 'static'),
        template_folder=str(UI_DIR / 'templates'),
    )
    app.config['JSON_SORT_KEYS'] = False

    codebook_spec = utils.load_codebook_spec()
    validation_ctx = build_context(codebook_spec)

    @app.route('/')
    def index() -> str:
        participants = utils.list_participants()
        total_tags = sum(item.get('tags_total', 0) for item in participants)
        return render_template(
            'ui/index.html',
            participants=participants,
            total_tags=total_tags,
            codebook=codebook_spec,
        )

    @app.route('/participant/<participant_id>')
    def participant(participant_id: str) -> str:
        participant_id = participant_id.upper()
        try:
            payload = utils.participant_payload(participant_id)
        except FileNotFoundError as exc:
            abort(404, description=str(exc))

        return render_template(
            'ui/participant-enhanced.html',
            participant=payload,
            codebook=codebook_spec,
        )

    @app.get('/api/codebook')
    def api_codebook() -> tuple[str, int, dict]:
        return jsonify(codebook_spec), 200, {'Cache-Control': 'no-store'}

    @app.post('/api/save/<participant_id>')
    def api_save(participant_id: str):
        participant_id = participant_id.upper()
        payload = request.get_json(force=True, silent=True)
        if not payload:
            return jsonify({'status': 'error', 'errors': ['Empty payload']}), 400

        preamble = payload.get('preamble', '')
        scenes_input = payload.get('scenes', [])

        if not isinstance(scenes_input, list):
            return jsonify({'status': 'error', 'errors': ['Scenes payload malformed']}), 400

        scenes: List[SceneSegment] = []
        for item in scenes_input:
            if not isinstance(item, dict):
                continue
            heading = item.get('heading', '')
            body = item.get('body', '')
            number = item.get('number') or _infer_scene_number(heading)
            scenes.append(SceneSegment(number=number, heading=heading, body=body))

        document = utils.rebuild_document(preamble, scenes)
        errors = validate_document(document, validation_ctx)
        if errors:
            return jsonify({'status': 'error', 'errors': errors}), 400

        md_path = utils.ensure_annotation_file(participant_id)
        utils.save_annotation_text(md_path, document)
        counts = utils.count_tags(document)
        return jsonify(
            {
                'status': 'ok',
                'message': f'Saved annotations for {participant_id}',
                'tag_counts': counts,
                'total_tags': sum(counts.values()),
            }
        )

    @app.post('/api/validate')
    def api_validate():
        payload = request.get_json(force=True, silent=True)
        if not payload:
            return jsonify({'status': 'error', 'errors': ['Empty payload']}), 400
        text = payload.get('text', '')
        errors = validate_document(text, validation_ctx)
        return jsonify({'status': 'ok', 'errors': errors})

    @app.get('/api/hypothesis-graph/<participant_id>')
    def api_hypothesis_graph(participant_id: str):
        """Get hypothesis evolution graph for a participant."""
        participant_id = participant_id.upper()
        try:
            text, _ = utils.load_annotation_text(participant_id)
            graph_data = get_hypothesis_graph(participant_id, text)
            return jsonify(graph_data)
        except FileNotFoundError as exc:
            return jsonify({'error': str(exc)}), 404

    @app.get('/api/analytics/<participant_id>')
    def api_analytics(participant_id: str):
        """Get comprehensive analytics for a participant."""
        participant_id = participant_id.upper()
        try:
            text, _ = utils.load_annotation_text(participant_id)
            preamble, scenes = utils.split_into_scenes(text)

            # Calculate scene boundaries
            scene_boundaries = []
            current_pos = len(preamble)
            for scene in scenes:
                start = current_pos
                end = start + len(scene.heading) + len(scene.body)
                scene_boundaries.append((start, end))
                current_pos = end

            usage_stats = calculate_code_usage_stats(text)
            incomplete_cycles = detect_incomplete_cycles(text)
            attribute_issues = detect_attribute_mismatches(text)
            timeline = generate_timeline_data(text, scene_boundaries)
            cross_scene = get_cross_scene_patterns(text, scene_boundaries)

            return jsonify({
                'usage_stats': usage_stats,
                'incomplete_cycles': incomplete_cycles,
                'attribute_issues': attribute_issues,
                'timeline': timeline,
                'cross_scene_patterns': cross_scene,
            })
        except FileNotFoundError as exc:
            return jsonify({'error': str(exc)}), 404

    @app.post('/api/validate-evidence')
    def api_validate_evidence():
        """Validate evidence citations against available panels."""
        payload = request.get_json(force=True, silent=True)
        if not payload:
            return jsonify({'status': 'error', 'errors': ['Empty payload']}), 400

        text = payload.get('text', '')
        available_panels = payload.get('panels', ['A', 'B', 'C', 'D', 'E', 'F'])

        issues = validate_evidence_citations(text, available_panels)
        return jsonify({'issues': issues})

    @app.get('/api/compare')
    def api_compare():
        """Compare annotations between two coders."""
        coder_a = request.args.get('coder_a', '').upper()
        coder_b = request.args.get('coder_b', '').upper()
        participant = request.args.get('participant', '').upper()

        if not all([coder_a, coder_b, participant]):
            return jsonify({'error': 'Missing required parameters'}), 400

        try:
            # Load annotations for both coders
            # Assuming naming convention: P01_CoderA.md, P01_CoderB.md
            path_a = Path('02_annotations') / f'{participant}_{coder_a}.md'
            path_b = Path('02_annotations') / f'{participant}_{coder_b}.md'

            if not path_a.exists() or not path_b.exists():
                return jsonify({'error': 'Annotation files not found'}), 404

            text_a = path_a.read_text(encoding='utf-8')
            text_b = path_b.read_text(encoding='utf-8')

            agreement = calculate_inter_rater_agreement(text_a, text_b)
            return jsonify(agreement)
        except Exception as exc:
            return jsonify({'error': str(exc)}), 500

    @app.get('/api/usage-dashboard')
    def api_usage_dashboard():
        """Get global usage statistics across all participants."""
        participants = utils.list_participants()
        all_stats = []

        for p in participants:
            if not p.get('has_annotation'):
                continue
            try:
                text, _ = utils.load_annotation_text(p['participant_id'])
                stats = calculate_code_usage_stats(text)
                stats['participant'] = p['participant_id']
                all_stats.append(stats)
            except Exception:
                continue

        # Aggregate statistics
        total_tags_by_code = {}
        total_participants = len(all_stats)

        for stats in all_stats:
            for code, count in stats.get('tag_counts', {}).items():
                total_tags_by_code[code] = total_tags_by_code.get(code, 0) + count

        return jsonify({
            'by_participant': all_stats,
            'aggregate': {
                'total_tags_by_code': total_tags_by_code,
                'total_participants': total_participants,
            },
        })

    @app.route('/dashboard')
    def dashboard():
        """Analytics dashboard page."""
        return render_template('ui/dashboard.html', codebook=codebook_spec)

    @app.route('/compare')
    def compare_page():
        """Inter-rater comparison page."""
        participants = utils.list_participants()
        return render_template(
            'ui/compare.html',
            participants=participants,
            codebook=codebook_spec,
        )

    return app


def _infer_scene_number(heading: str) -> int:
    pattern = utils._scene_regex()  # type: ignore[attr-defined]
    match = pattern.search(heading)
    if match:
        try:
            raw_num = match.group('num')
        except IndexError:
            raw_num = match.group(1)
        return int(raw_num)
    # Fallback: look for digits
    digits = ''.join(filter(str.isdigit, heading))
    return int(digits) if digits else 0

