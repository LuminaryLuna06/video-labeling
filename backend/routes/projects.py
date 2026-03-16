from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timezone
from bson import ObjectId
from utils.auth_middleware import token_required

projects_bp = Blueprint('projects', __name__)


def serialize_project(project):
    result = {
        'id': str(project['_id']),
        'name': project['name'],
        'description': project.get('description', ''),
        'project_type': project.get('project_type', 'video'),  # 'video' or 'image'
        'status': project.get('status', 'active'),
        'created_by': str(project['created_by']),
        'created_at': project['created_at'].isoformat(),
        'updated_at': project.get('updated_at', project['created_at']).isoformat()
    }
    # Include task_type for image projects
    if project.get('task_type'):
        result['task_type'] = project['task_type']
    return result


def serialize_subpart(subpart):
    return {
        'id': str(subpart['_id']),
        'project_id': str(subpart['project_id']),
        'name': subpart['name'],
        'description': subpart.get('description', ''),
        'assigned_users': [str(uid) for uid in subpart.get('assigned_users', [])],
        'reviewer': str(subpart['reviewer']) if subpart.get('reviewer') else None,
        'reviewers': [str(rid) for rid in subpart.get('reviewers', [])],
        'order': subpart.get('order', 0),
        'status': subpart.get('status', 'pending'),
        'created_at': subpart['created_at'].isoformat()
    }


# ============ PROJECT ROUTES ============

@projects_bp.route('', methods=['POST'])
@token_required
def create_project():
    data = request.get_json()
    
    if not data or not data.get('name'):
        return jsonify({'error': 'Project name is required'}), 400

    project_type = data.get('project_type', 'video')
    
    if project_type not in ['video', 'image']:
        return jsonify({'error': 'Invalid project type. Must be "video" or "image"'}), 400

    task_type = data.get('task_type')
    
    if project_type == 'image' and task_type:
        if task_type not in ['object_detection', 'classification', 'captioning', 'qa', 'segmentation']:
            return jsonify({'error': 'Invalid task type'}), 400

    project = {
        'name': data['name'],
        'description': data.get('description', ''),
        'project_type': project_type,
        'status': 'active',
        'created_by': request.current_user['_id'],
        'created_at': datetime.now(timezone.utc),
        'updated_at': datetime.now(timezone.utc)
    }

    # Add task_type for image projects
    if project_type == 'image' and task_type:
        project['task_type'] = task_type

    result = current_app.db.projects.insert_one(project)
    project['_id'] = result.inserted_id

    return jsonify(serialize_project(project)), 201


@projects_bp.route('', methods=['GET'])
@token_required
def get_projects():
    user_id = request.current_user['_id']
    role = request.current_user.get('role', 'annotator')

    if role == 'admin':
        projects = list(current_app.db.projects.find())
    else:
        # Get projects where user is creator, assigned to a subpart, or reviewer
        assigned_subparts = current_app.db.subparts.find({
            '$or': [
                {'assigned_users': user_id},
                {'reviewer': user_id}
            ]
        })
        assigned_project_ids = list(set(s['project_id'] for s in assigned_subparts))

        projects = list(current_app.db.projects.find({
            '$or': [
                {'created_by': user_id},
                {'_id': {'$in': assigned_project_ids}}
            ]
        }))

    result = []
    for p in projects:
        proj_data = serialize_project(p)
        project_type = p.get('project_type', 'video')
        # Count subparts and videos/images
        proj_data['subpart_count'] = current_app.db.subparts.count_documents({'project_id': p['_id']})
        if project_type == 'image':
            proj_data['image_count'] = current_app.db.images.count_documents({'project_id': p['_id']})
            proj_data['video_count'] = 0
        else:
            proj_data['video_count'] = current_app.db.videos.count_documents({'project_id': p['_id']})
            proj_data['image_count'] = 0
        # Get creator info
        creator = current_app.db.users.find_one({'_id': p['created_by']}, {'password_hash': 0})
        if creator:
            proj_data['creator_name'] = creator.get('full_name') or creator['username']
        result.append(proj_data)

    return jsonify(result)


@projects_bp.route('/<project_id>', methods=['GET'])
@token_required
def get_project(project_id):
    try:
        project = current_app.db.projects.find_one({'_id': ObjectId(project_id)})
    except Exception:
        return jsonify({'error': 'Invalid project ID'}), 400

    if not project:
        return jsonify({'error': 'Project not found'}), 404

    proj_data = serialize_project(project)

    # Get subparts with user details (sorted by created_at descending - newest first)
    subparts = list(current_app.db.subparts.find({'project_id': ObjectId(project_id)}).sort('created_at', -1))
    proj_data['subparts'] = []
    project_type = project.get('project_type', 'video')
    
    for sp in subparts:
        sp_data = serialize_subpart(sp)
        # Get assigned user details
        sp_data['assigned_user_details'] = []
        for uid in sp.get('assigned_users', []):
            user = current_app.db.users.find_one({'_id': uid}, {'password_hash': 0})
            if user:
                sp_data['assigned_user_details'].append({
                    'id': str(user['_id']),
                    'username': user['username'],
                    'full_name': user.get('full_name', ''),
                    'avatar_color': user.get('avatar_color', '#4A90D9')
                })
        
        # Count based on project type
        if project_type == 'image':
            sp_data['image_count'] = current_app.db.images.count_documents({'subpart_id': ObjectId(sp['_id'])})
            sp_data['video_count'] = 0
        else:
            sp_data['video_count'] = current_app.db.videos.count_documents({'subpart_id': ObjectId(sp['_id'])})
            sp_data['image_count'] = 0
        
        # Get reviewer details (legacy single reviewer)
        if sp.get('reviewer'):
            reviewer = current_app.db.users.find_one({'_id': sp['reviewer']}, {'password_hash': 0})
            if reviewer:
                sp_data['reviewer_details'] = {
                    'id': str(reviewer['_id']),
                    'username': reviewer['username'],
                    'full_name': reviewer.get('full_name', ''),
                    'avatar_color': reviewer.get('avatar_color', '#4A90D9')
                }
        # Get multiple reviewers details
        sp_data['reviewers'] = [str(rid) for rid in sp.get('reviewers', [])]
        sp_data['reviewer_details_list'] = []
        for rid in sp.get('reviewers', []):
            reviewer = current_app.db.users.find_one({'_id': rid}, {'password_hash': 0})
            if reviewer:
                sp_data['reviewer_details_list'].append({
                    'id': str(reviewer['_id']),
                    'username': reviewer['username'],
                    'full_name': reviewer.get('full_name', ''),
                    'avatar_color': reviewer.get('avatar_color', '#4A90D9')
                })
        proj_data['subparts'].append(sp_data)

    # Get videos or images based on project type
    if project_type == 'image':
        images = list(current_app.db.images.find({'project_id': ObjectId(project_id)}))
        proj_data['images'] = []
        for img in images:
            proj_data['images'].append({
                'id': str(img['_id']),
                'filename': img['filename'],
                'original_name': img['original_name'],
                'width': img.get('width', 0),
                'height': img.get('height', 0),
                'status': img.get('status', 'uploaded'),
                'subpart_id': str(img.get('subpart_id', '')),
                'uploaded_by': str(img['uploaded_by']),
                'created_at': img['created_at'].isoformat()
            })
        proj_data['videos'] = []
    else:
        # Get videos
        videos = list(current_app.db.videos.find({'project_id': ObjectId(project_id)}))
        proj_data['videos'] = []
        for v in videos:
            proj_data['videos'].append({
                'id': str(v['_id']),
                'filename': v['filename'],
                'original_name': v['original_name'],
                'duration': v.get('duration', 0),
                'status': v.get('status', 'uploaded'),
                'subpart_id': str(v.get('subpart_id', '')),
                'uploaded_by': str(v['uploaded_by']),
                'created_at': v['created_at'].isoformat()
            })
        proj_data['images'] = []

    return jsonify(proj_data)


@projects_bp.route('/<project_id>', methods=['PUT'])
@token_required
def update_project(project_id):
    data = request.get_json()
    try:
        project = current_app.db.projects.find_one({'_id': ObjectId(project_id)})
    except Exception:
        return jsonify({'error': 'Invalid project ID'}), 400

    if not project:
        return jsonify({'error': 'Project not found'}), 404

    update_fields = {}
    if 'name' in data:
        update_fields['name'] = data['name']
    if 'description' in data:
        update_fields['description'] = data['description']
    if 'status' in data:
        update_fields['status'] = data['status']
    if 'task_type' in data:
        # Validate task_type
        valid_task_types = ['object_detection', 'classification', 'captioning', 'qa', 'segmentation']
        if data['task_type'] in valid_task_types:
            update_fields['task_type'] = data['task_type']
    update_fields['updated_at'] = datetime.now(timezone.utc)

    current_app.db.projects.update_one(
        {'_id': ObjectId(project_id)},
        {'$set': update_fields}
    )

    updated = current_app.db.projects.find_one({'_id': ObjectId(project_id)})
    return jsonify(serialize_project(updated))


@projects_bp.route('/<project_id>', methods=['DELETE'])
@token_required
def delete_project(project_id):
    try:
        project = current_app.db.projects.find_one({'_id': ObjectId(project_id)})
    except Exception:
        return jsonify({'error': 'Invalid project ID'}), 400

    if not project:
        return jsonify({'error': 'Project not found'}), 404

    project_type = project.get('project_type', 'video')

    if project_type == 'image':
        # Delete image-related data
        image_ids = [img['_id'] for img in current_app.db.images.find({'project_id': ObjectId(project_id)})]
        current_app.db.image_captions.delete_many({'image_id': {'$in': image_ids}})
        current_app.db.image_regions.delete_many({'image_id': {'$in': image_ids}})
        current_app.db.image_qa.delete_many({'image_id': {'$in': image_ids}})
        current_app.db.images.delete_many({'project_id': ObjectId(project_id)})
    else:
        # Delete video-related data
        video_ids = [v['_id'] for v in current_app.db.videos.find({'project_id': ObjectId(project_id)})]
        segment_ids = [s['_id'] for s in current_app.db.video_segments.find({'video_id': {'$in': video_ids}})]
        current_app.db.captions.delete_many({'segment_id': {'$in': segment_ids}})
        current_app.db.object_regions.delete_many({'segment_id': {'$in': segment_ids}})
        current_app.db.video_segments.delete_many({'video_id': {'$in': video_ids}})
        current_app.db.videos.delete_many({'project_id': ObjectId(project_id)})

    current_app.db.subparts.delete_many({'project_id': ObjectId(project_id)})
    current_app.db.tags.delete_many({'project_id': ObjectId(project_id)})
    current_app.db.categories.delete_many({'project_id': ObjectId(project_id)})
    current_app.db.projects.delete_one({'_id': ObjectId(project_id)})

    return jsonify({'message': 'Project deleted successfully'})


# ============ SUBPART ROUTES ============

@projects_bp.route('/<project_id>/subparts', methods=['POST'])
@token_required
def create_subpart(project_id):
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'Subpart name is required'}), 400

    try:
        project = current_app.db.projects.find_one({'_id': ObjectId(project_id)})
    except Exception:
        return jsonify({'error': 'Invalid project ID'}), 400

    if not project:
        return jsonify({'error': 'Project not found'}), 404

    # Get next order
    max_order = current_app.db.subparts.find_one(
        {'project_id': ObjectId(project_id)},
        sort=[('order', -1)]
    )
    next_order = (max_order['order'] + 1) if max_order else 0

    assigned_users = []
    for uid in data.get('assigned_users', []):
        try:
            assigned_users.append(ObjectId(uid))
        except Exception:
            pass

    # Process multiple reviewers
    reviewers = []
    for rid in data.get('reviewers', []):
        try:
            reviewers.append(ObjectId(rid))
        except Exception:
            pass

    subpart = {
        'project_id': ObjectId(project_id),
        'name': data['name'],
        'description': data.get('description', ''),
        'assigned_users': assigned_users,
        'reviewer': ObjectId(data['reviewer']) if data.get('reviewer') else None,
        'reviewers': reviewers,
        'order': next_order,
        'status': 'pending',
        'created_at': datetime.now(timezone.utc),
        'updated_at': datetime.now(timezone.utc)
    }

    result = current_app.db.subparts.insert_one(subpart)
    subpart['_id'] = result.inserted_id

    return jsonify(serialize_subpart(subpart)), 201


@projects_bp.route('/<project_id>/subparts/<subpart_id>', methods=['PUT'])
@token_required
def update_subpart(project_id, subpart_id):
    data = request.get_json()

    try:
        subpart = current_app.db.subparts.find_one({
            '_id': ObjectId(subpart_id),
            'project_id': ObjectId(project_id)
        })
    except Exception:
        return jsonify({'error': 'Invalid ID'}), 400

    if not subpart:
        return jsonify({'error': 'Subpart not found'}), 404

    update_fields = {}
    if 'name' in data:
        update_fields['name'] = data['name']
    if 'description' in data:
        update_fields['description'] = data['description']
    if 'status' in data:
        update_fields['status'] = data['status']
    if 'assigned_users' in data:
        update_fields['assigned_users'] = [ObjectId(uid) for uid in data['assigned_users']]
    if 'reviewer' in data:
        update_fields['reviewer'] = ObjectId(data['reviewer']) if data['reviewer'] else None
    if 'reviewers' in data:
        update_fields['reviewers'] = [ObjectId(rid) for rid in data['reviewers']]
    if 'order' in data:
        update_fields['order'] = data['order']
    update_fields['updated_at'] = datetime.now(timezone.utc)

    current_app.db.subparts.update_one(
        {'_id': ObjectId(subpart_id)},
        {'$set': update_fields}
    )

    updated = current_app.db.subparts.find_one({'_id': ObjectId(subpart_id)})
    return jsonify(serialize_subpart(updated))


@projects_bp.route('/<project_id>/subparts/<subpart_id>', methods=['DELETE'])
@token_required
def delete_subpart(project_id, subpart_id):
    try:
        result = current_app.db.subparts.delete_one({
            '_id': ObjectId(subpart_id),
            'project_id': ObjectId(project_id)
        })
    except Exception:
        return jsonify({'error': 'Invalid ID'}), 400

    if result.deleted_count == 0:
        return jsonify({'error': 'Subpart not found'}), 404

    # Update videos that belonged to this subpart
    current_app.db.videos.update_many(
        {'subpart_id': ObjectId(subpart_id)},
        {'$unset': {'subpart_id': ''}}
    )

    return jsonify({'message': 'Subpart deleted successfully'})


# ============ EXPORT ROUTES ============

@projects_bp.route('/<project_id>/export/<format_type>', methods=['GET'])
@token_required
def export_project(project_id, format_type):
    """
    Export project data in various formats.
    Supported formats:
    - json: Full JSON export
    - yolo: YOLO format (for object detection)
    - coco: COCO format (for object detection/segmentation)
    - csv: CSV format (for classification/captioning)
    """
    try:
        project = current_app.db.projects.find_one({'_id': ObjectId(project_id)})
    except Exception:
        return jsonify({'error': 'Invalid project ID'}), 400
    
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    project_type = project.get('project_type', 'video')
    task_type = project.get('task_type', 'object_detection')
    
    if project_type == 'image':
        return export_image_project(project_id, project, task_type, format_type)
    else:
        return export_video_project(project_id, project, format_type)


def export_image_project(project_id, project, task_type, format_type):
    """Export image project data"""
    # Get all images in project
    images = list(current_app.db.images.find({'project_id': ObjectId(project_id)}))
    
    if format_type == 'json':
        return export_images_json(images, project)
    elif format_type == 'yolo':
        return export_images_yolo(images, project)
    elif format_type == 'coco':
        return export_images_coco(images, project)
    elif format_type == 'csv':
        return export_images_csv(images, project, task_type)
    else:
        return jsonify({'error': f'Unsupported format: {format_type}'}), 400


def export_video_project(project_id, project, format_type):
    """Export video project data"""
    videos = list(current_app.db.videos.find({'project_id': ObjectId(project_id)}))
    
    if format_type == 'json':
        return export_videos_json(videos, project)
    else:
        return jsonify({'error': f'Format {format_type} not supported for video projects'}), 400


def export_images_json(images, project):
    """Export full JSON"""
    data = {
        'project': serialize_project(project),
        'images': []
    }
    
    for img in images:
        img_data = {
            'id': str(img['_id']),
            'filename': img.get('original_name', ''),
            'width': img.get('width', 0),
            'height': img.get('height', 0),
            'regions': [],
            'classification': img.get('classification', {}),
            'caption': img.get('caption', {}),
            'qa_pairs': []
        }
        
        # Get regions
        regions = list(current_app.db.image_regions.find({'image_id': img['_id']}))
        for region in regions:
            img_data['regions'].append({
                'label': region.get('label', ''),
                'bbox': region.get('bbox', []),
                'mask_url': region.get('mask_url', ''),
                'caption': region.get('caption', {})
            })
        
        # Get QA pairs
        qa_pairs = list(current_app.db.image_qa.find({'image_id': img['_id']}))
        for qa in qa_pairs:
            img_data['qa_pairs'].append({
                'question': qa.get('question', ''),
                'answer': qa.get('answer', ''),
                'question_vi': qa.get('question_vi', ''),
                'answer_vi': qa.get('answer_vi', ''),
                'qa_type': qa.get('qa_type', 'general')
            })
        
        data['images'].append(img_data)
    
    return jsonify(data)


def export_images_yolo(images, project):
    """Export in YOLO format (txt files content)"""
    # Collect all unique labels
    all_labels = set()
    for img in images:
        regions = list(current_app.db.image_regions.find({'image_id': img['_id']}))
        for region in regions:
            if region.get('label'):
                all_labels.add(region['label'])
    
    label_to_id = {label: idx for idx, label in enumerate(sorted(all_labels))}
    
    data = {
        'format': 'yolo',
        'classes': list(label_to_id.keys()),
        'annotations': []
    }
    
    for img in images:
        img_width = img.get('width', 1)
        img_height = img.get('height', 1)
        
        regions = list(current_app.db.image_regions.find({'image_id': img['_id']}))
        
        yolo_annotations = []
        for region in regions:
            if region.get('bbox') and region.get('label'):
                bbox = region['bbox']  # [x, y, width, height]
                label_id = label_to_id.get(region['label'], 0)
                
                # Convert to YOLO format: class x_center y_center width height (normalized)
                x_center = (bbox[0] + bbox[2] / 2) / img_width
                y_center = (bbox[1] + bbox[3] / 2) / img_height
                width = bbox[2] / img_width
                height = bbox[3] / img_height
                
                yolo_annotations.append(f"{label_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}")
        
        data['annotations'].append({
            'image': img.get('original_name', ''),
            'txt_content': '\n'.join(yolo_annotations)
        })
    
    return jsonify(data)


def export_images_coco(images, project):
    """Export in COCO format"""
    # Collect all unique labels
    all_labels = set()
    for img in images:
        regions = list(current_app.db.image_regions.find({'image_id': img['_id']}))
        for region in regions:
            if region.get('label'):
                all_labels.add(region['label'])
    
    label_to_id = {label: idx + 1 for idx, label in enumerate(sorted(all_labels))}
    
    coco_data = {
        'info': {
            'description': project.get('name', 'Exported Project'),
            'version': '1.0',
            'year': datetime.now().year
        },
        'categories': [
            {'id': idx, 'name': label, 'supercategory': 'object'}
            for label, idx in label_to_id.items()
        ],
        'images': [],
        'annotations': []
    }
    
    annotation_id = 1
    for img_idx, img in enumerate(images):
        img_id = img_idx + 1
        
        coco_data['images'].append({
            'id': img_id,
            'file_name': img.get('original_name', ''),
            'width': img.get('width', 0),
            'height': img.get('height', 0)
        })
        
        regions = list(current_app.db.image_regions.find({'image_id': img['_id']}))
        for region in regions:
            if region.get('bbox') and region.get('label'):
                bbox = region['bbox']  # [x, y, width, height]
                
                coco_data['annotations'].append({
                    'id': annotation_id,
                    'image_id': img_id,
                    'category_id': label_to_id.get(region['label'], 1),
                    'bbox': bbox,
                    'area': bbox[2] * bbox[3],
                    'iscrowd': 0
                })
                annotation_id += 1
    
    return jsonify(coco_data)


def export_images_csv(images, project, task_type):
    """Export in CSV format (for classification/captioning)"""
    import csv
    from io import StringIO
    
    output = StringIO()
    
    if task_type == 'classification':
        writer = csv.writer(output)
        writer.writerow(['filename', 'labels', 'primary_label', 'notes'])
        
        for img in images:
            classification = img.get('classification', {})
            labels = ','.join(classification.get('labels', []))
            writer.writerow([
                img.get('original_name', ''),
                labels,
                classification.get('primary_label', ''),
                classification.get('notes', '')
            ])
    
    elif task_type == 'captioning':
        writer = csv.writer(output)
        writer.writerow(['filename', 'visual_caption', 'contextual_caption', 'combined_caption',
                        'visual_caption_vi', 'contextual_caption_vi', 'combined_caption_vi'])
        
        for img in images:
            caption = img.get('caption', {})
            writer.writerow([
                img.get('original_name', ''),
                caption.get('visual_caption', ''),
                caption.get('contextual_caption', ''),
                caption.get('combined_caption', ''),
                caption.get('visual_caption_vi', ''),
                caption.get('contextual_caption_vi', ''),
                caption.get('combined_caption_vi', '')
            ])
    
    elif task_type == 'qa':
        writer = csv.writer(output)
        writer.writerow(['filename', 'question', 'answer', 'question_vi', 'answer_vi', 'qa_type'])
        
        for img in images:
            qa_pairs = list(current_app.db.image_qa.find({'image_id': img['_id']}))
            for qa in qa_pairs:
                writer.writerow([
                    img.get('original_name', ''),
                    qa.get('question', ''),
                    qa.get('answer', ''),
                    qa.get('question_vi', ''),
                    qa.get('answer_vi', ''),
                    qa.get('qa_type', 'general')
                ])
    
    else:
        # Default: basic info
        writer = csv.writer(output)
        writer.writerow(['filename', 'width', 'height', 'region_count'])
        
        for img in images:
            region_count = current_app.db.image_regions.count_documents({'image_id': img['_id']})
            writer.writerow([
                img.get('original_name', ''),
                img.get('width', 0),
                img.get('height', 0),
                region_count
            ])
    
    return jsonify({
        'format': 'csv',
        'task_type': task_type,
        'csv_content': output.getvalue()
    })


def export_videos_json(videos, project):
    """Export video project as JSON"""
    data = {
        'project': serialize_project(project),
        'videos': []
    }
    
    for video in videos:
        video_data = {
            'id': str(video['_id']),
            'filename': video.get('original_name', ''),
            'duration': video.get('duration', 0),
            'fps': video.get('fps', 0),
            'segments': []
        }
        
        # Get segments
        segments = list(current_app.db.segments.find({'video_id': video['_id']}))
        for seg in segments:
            video_data['segments'].append({
                'start_time': seg.get('start_time', 0),
                'end_time': seg.get('end_time', 0),
                'label': seg.get('label', ''),
                'caption': seg.get('caption', {}),
                'description': seg.get('description', '')
            })
        
        data['videos'].append(video_data)
    
    return jsonify(data)
