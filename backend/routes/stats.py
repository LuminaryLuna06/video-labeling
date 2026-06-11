from flask import Blueprint, jsonify, current_app
from utils.auth_middleware import token_required

stats_bp = Blueprint('stats', __name__)


@stats_bp.route('/video-duration', methods=['GET'])
@token_required
def video_duration_stats():
    try:
        video_projects = list(current_app.db.projects.find(
            {'project_type': 'video'}, {'_id': 1}
        ))
        project_ids = [p['_id'] for p in video_projects]

        if not project_ids:
            return jsonify({'S': 0, 'M': 0, 'L': 0, 'other': 0, 'total': 0})

        pipeline = [
            {'$match': {'project_id': {'$in': project_ids}}},
            {'$group': {
                '_id': {
                    '$switch': {
                        'branches': [
                            {
                                'case': {'$and': [{'$gte': ['$duration', 30]}, {'$lt': ['$duration', 60]}]},
                                'then': 'S'
                            },
                            {
                                'case': {'$and': [{'$gte': ['$duration', 60]}, {'$lt': ['$duration', 300]}]},
                                'then': 'M'
                            },
                            {
                                'case': {'$and': [{'$gte': ['$duration', 300]}, {'$lt': ['$duration', 600]}]},
                                'then': 'L'
                            },
                        ],
                        'default': 'other'
                    }
                },
                'count': {'$sum': 1}
            }}
        ]

        results = list(current_app.db.videos.aggregate(pipeline))
        stats: dict = {'S': 0, 'M': 0, 'L': 0, 'other': 0}
        for r in results:
            bucket = r['_id']
            if bucket in stats:
                stats[bucket] = r['count']
        stats['total'] = sum(stats.values())
        return jsonify(stats)

    except Exception as e:
        return jsonify({'error': str(e)}), 500
