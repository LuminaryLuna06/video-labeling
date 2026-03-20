import os
import uuid
import base64
from io import BytesIO
import cv2
import numpy as np
import requests
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timezone
from bson import ObjectId
from PIL import Image as PILImage
from werkzeug.utils import secure_filename
from config import Config
from utils.auth_middleware import token_required
from utils.vector_store import upsert_embedding, search_embeddings

images_bp = Blueprint('images', __name__)

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'bmp', 'gif'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _serialize_object_id_list(values):
    """Convert ObjectId list (or mixed values) to string list for JSON responses."""
    if not values:
        return []
    result = []
    for value in values:
        try:
            result.append(str(value))
        except Exception:
            continue
    return result


def _build_image_stats(db, image):
    """Build image dict with annotation statistics."""
    img_id = image['_id']
    
    # Count annotations
    regions_count = db.image_regions.count_documents({'image_id': img_id})
    qa_count = db.image_qa.count_documents({'image_id': img_id})
    has_caption = db.image_captions.count_documents({'image_id': img_id}) > 0
    has_classification = bool(image.get('classification'))
    object_indexed_count = db.image_regions.count_documents({'image_id': img_id, 'indexed': True})
    
    # Get region labels (for quick labels feature)
    regions = list(db.image_regions.find({'image_id': img_id}, {'label': 1}))
    region_labels = [r.get('label', '') for r in regions if r.get('label')]
    
    thumb = image.get('thumbnail', '')
    
    # Resolve tag names
    image_tags = image.get('tags', [])
    tag_ids = []
    for t in image_tags:
        try:
            tag_ids.append(ObjectId(t) if not isinstance(t, ObjectId) else t)
        except Exception:
            pass
    tags_data = []
    if tag_ids:
        tags = list(db.tags.find({'_id': {'$in': tag_ids}}))
        tags_data = [str(t['_id']) for t in tags]

    return {
        'id': str(img_id),
        'filename': image['filename'],
        'original_name': image['original_name'],
        'file_size': image.get('file_size', 0),
        'width': image.get('width', 0),
        'height': image.get('height', 0),
        'status': image.get('status', 'uploaded'),
        'current_step': image.get('current_step', 1),
        'project_id': str(image['project_id']) if image.get('project_id') else None,
        'subpart_id': str(image['subpart_id']) if image.get('subpart_id') else None,
        'url': f'/uploads/images/{image["filename"]}',
        'thumbnail_url': f'/uploads/thumbnails/{thumb}' if thumb else f'/uploads/images/{image["filename"]}',
        'uploaded_by': str(image['uploaded_by']),
        'annotators': [str(a) for a in image.get('annotators', [])],
        'regions_count': regions_count,
        'region_labels': region_labels,
        'qa_count': qa_count,
        'has_caption': has_caption,
        'has_classification': has_classification,
        'classification': image.get('classification'),
        'knowledge_base_ids': image.get('knowledge_base_ids', []),
        'tags': tags_data,
        'review_status': image.get('review_status', 'not_submitted'),
        'review_comment': image.get('review_comment', ''),
        'reviewed_by': str(image['reviewed_by']) if image.get('reviewed_by') else None,
        'reviews': _format_reviews(image.get('reviews', [])),
        'reviewers': [str(r) for r in image.get('reviewers', [])],
        'indexed': bool(image.get('indexed', False)),
        'indexed_regions': int(image.get('indexed_regions', 0)),
        'object_indexed_count': object_indexed_count,
        'objects_indexed_complete': regions_count > 0 and object_indexed_count >= regions_count,
        'indexed_at': image['indexed_at'].isoformat() if image.get('indexed_at') else None,
        'created_at': image['created_at'].isoformat()
    }


def _format_reviews(reviews):
    """Format review entries for API response."""
    formatted = []
    for r in reviews:
        formatted.append({
            'reviewer_id': str(r['reviewer_id']),
            'action': r['action'],
            'comment': r.get('comment', ''),
            'reviewed_at': r['reviewed_at'].isoformat() if r.get('reviewed_at') else None
        })
    return formatted


@images_bp.route('/upload', methods=['POST'])
@token_required
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400

    file = request.files['image']
    project_id = request.form.get('project_id')
    subpart_id = request.form.get('subpart_id')

    if not project_id:
        return jsonify({'error': 'Project ID is required'}), 400

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': f'File type not allowed. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'}), 400

    # Verify project exists and is image type
    try:
        project = current_app.db.projects.find_one({'_id': ObjectId(project_id)})
    except Exception:
        return jsonify({'error': 'Invalid project ID'}), 400

    if not project:
        return jsonify({'error': 'Project not found'}), 404

    # Generate unique filename
    original_name = secure_filename(file.filename)
    ext = original_name.rsplit('.', 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{ext}"

    # Ensure images directory exists
    images_dir = os.path.join(Config.UPLOAD_FOLDER, 'images')
    os.makedirs(images_dir, exist_ok=True)

    # Save file
    filepath = os.path.join(images_dir, unique_filename)
    file.save(filepath)

    # Get file size
    file_size = os.path.getsize(filepath)

    image_doc = {
        'project_id': ObjectId(project_id),
        'subpart_id': ObjectId(subpart_id) if subpart_id else None,
        'filename': unique_filename,
        'original_name': original_name,
        'file_path': filepath,
        'file_size': file_size,
        'width': int(request.form.get('width', 0)),
        'height': int(request.form.get('height', 0)),
        'status': 'uploaded',
        'current_step': 1,
        'annotators': [],
        'classification': None,
        'indexed': False,
        'indexed_regions': 0,
        'uploaded_by': request.current_user['_id'],
        'created_at': datetime.now(timezone.utc),
        'updated_at': datetime.now(timezone.utc)
    }

    result = current_app.db.images.insert_one(image_doc)

    return jsonify({
        'id': str(result.inserted_id),
        'filename': unique_filename,
        'original_name': original_name,
        'file_size': file_size,
        'url': f'/uploads/images/{unique_filename}',
        'status': 'uploaded',
        'message': 'Image uploaded successfully'
    }), 201


@images_bp.route('/upload-batch', methods=['POST'])
@token_required
def upload_images_batch():
    """Upload multiple images at once."""
    if 'images' not in request.files:
        return jsonify({'error': 'No image files provided'}), 400

    files = request.files.getlist('images')
    project_id = request.form.get('project_id')
    subpart_id = request.form.get('subpart_id')

    if not project_id:
        return jsonify({'error': 'Project ID is required'}), 400

    if not files:
        return jsonify({'error': 'No files selected'}), 400

    # Verify project exists
    try:
        project = current_app.db.projects.find_one({'_id': ObjectId(project_id)})
    except Exception:
        return jsonify({'error': 'Invalid project ID'}), 400

    if not project:
        return jsonify({'error': 'Project not found'}), 404

    images_dir = os.path.join(Config.UPLOAD_FOLDER, 'images')
    os.makedirs(images_dir, exist_ok=True)

    uploaded = []
    errors = []

    for file in files:
        if file.filename == '':
            continue

        if not allowed_file(file.filename):
            errors.append({'filename': file.filename, 'error': 'File type not allowed'})
            continue

        try:
            original_name = secure_filename(file.filename)
            ext = original_name.rsplit('.', 1)[1].lower()
            unique_filename = f"{uuid.uuid4().hex}.{ext}"
            filepath = os.path.join(images_dir, unique_filename)
            file.save(filepath)
            file_size = os.path.getsize(filepath)

            image_doc = {
                'project_id': ObjectId(project_id),
                'subpart_id': ObjectId(subpart_id) if subpart_id else None,
                'filename': unique_filename,
                'original_name': original_name,
                'file_path': filepath,
                'file_size': file_size,
                'width': 0,
                'height': 0,
                'status': 'uploaded',
                'current_step': 1,
                'annotators': [],
                'classification': None,
                'indexed': False,
                'indexed_regions': 0,
                'uploaded_by': request.current_user['_id'],
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc)
            }

            result = current_app.db.images.insert_one(image_doc)
            uploaded.append({
                'id': str(result.inserted_id),
                'filename': unique_filename,
                'original_name': original_name,
                'url': f'/uploads/images/{unique_filename}'
            })
        except Exception as e:
            errors.append({'filename': file.filename, 'error': str(e)})

    return jsonify({
        'uploaded': uploaded,
        'errors': errors,
        'total_uploaded': len(uploaded),
        'total_errors': len(errors)
    }), 201


@images_bp.route('/project/<project_id>', methods=['GET'])
@token_required
def get_project_images(project_id):
    try:
        images = list(current_app.db.images.find({'project_id': ObjectId(project_id)}))
    except Exception:
        return jsonify({'error': 'Invalid project ID'}), 400

    result = [_build_image_stats(current_app.db, img) for img in images]
    return jsonify(result)


@images_bp.route('/subpart/<subpart_id>', methods=['GET'])
@token_required
def get_subpart_images(subpart_id):
    try:
        images = list(current_app.db.images.find({'subpart_id': ObjectId(subpart_id)}).sort('created_at', -1))
    except Exception:
        return jsonify({'error': 'Invalid subpart ID'}), 400

    result = [_build_image_stats(current_app.db, img) for img in images]
    return jsonify(result)


@images_bp.route('/subpart/<subpart_id>/project', methods=['GET'])
@token_required
def get_subpart_project(subpart_id):
    """Get project_id from subpart_id"""
    try:
        subpart = current_app.db.subparts.find_one({'_id': ObjectId(subpart_id)})
    except Exception:
        return jsonify({'error': 'Invalid subpart ID'}), 400

    if not subpart:
        return jsonify({'error': 'Subpart not found'}), 404

    return jsonify({'project_id': str(subpart['project_id'])})


@images_bp.route('/<image_id>', methods=['GET'])
@token_required
def get_image(image_id):
    try:
        image = current_app.db.images.find_one({'_id': ObjectId(image_id)})
    except Exception:
        return jsonify({'error': 'Invalid image ID'}), 400

    if not image:
        return jsonify({'error': 'Image not found'}), 404

    result = _build_image_stats(current_app.db, image)
    
    # Get regions with captions
    regions = list(current_app.db.image_regions.find({'image_id': ObjectId(image_id)}))
    result['regions'] = []
    for r in regions:
        region_data = {
            'id': str(r['_id']),
            'image_id': str(r['image_id']),
            'label': r.get('label', ''),
            'color': r.get('color', '#FF0000'),
            'category_id': str(r['category_id']) if r.get('category_id') else None,
            'bbox': r.get('bbox'),  # [x, y, width, height]
            'segmentation_mask': r.get('segmentation_mask', ''),
            'brush_mask': r.get('brush_mask', ''),
            'knowledge_base_ids': r.get('knowledge_base_ids', []),
            'indexed': bool(r.get('indexed', False)),
            'indexed_at': r['indexed_at'].isoformat() if r.get('indexed_at') else None,
            'created_at': r['created_at'].isoformat()
        }
        # Get region caption
        caption = current_app.db.image_captions.find_one({'region_id': r['_id']})
        if caption:
            region_data['caption'] = {
                'id': str(caption['_id']),
                'visual_caption': caption.get('visual_caption', ''),
                'contextual_caption': caption.get('contextual_caption', ''),
                'knowledge_caption': caption.get('knowledge_caption', ''),
                'combined_caption': caption.get('combined_caption', ''),
                'visual_caption_vi': caption.get('visual_caption_vi', ''),
                'contextual_caption_vi': caption.get('contextual_caption_vi', ''),
                'knowledge_caption_vi': caption.get('knowledge_caption_vi', ''),
                'combined_caption_vi': caption.get('combined_caption_vi', ''),
                'knowledge_base_ids': _serialize_object_id_list(caption.get('knowledge_base_ids', []))
            }
        result['regions'].append(region_data)

    # Get image-level caption
    img_caption = current_app.db.image_captions.find_one({
        'image_id': ObjectId(image_id),
        'region_id': None
    })
    if img_caption:
        result['image_caption'] = {
            'id': str(img_caption['_id']),
            'visual_caption': img_caption.get('visual_caption', ''),
            'contextual_caption': img_caption.get('contextual_caption', ''),
            'knowledge_caption': img_caption.get('knowledge_caption', ''),
            'combined_caption': img_caption.get('combined_caption', ''),
            'visual_caption_vi': img_caption.get('visual_caption_vi', ''),
            'contextual_caption_vi': img_caption.get('contextual_caption_vi', ''),
            'knowledge_caption_vi': img_caption.get('knowledge_caption_vi', ''),
            'combined_caption_vi': img_caption.get('combined_caption_vi', ''),
            'knowledge_base_ids': _serialize_object_id_list(img_caption.get('knowledge_base_ids', []))
        }

    # Get QA pairs
    qa_pairs = list(current_app.db.image_qa.find({'image_id': ObjectId(image_id)}))
    result['qa_pairs'] = [{
        'id': str(qa['_id']),
        'question': qa.get('question', ''),
        'answer': qa.get('answer', ''),
        'question_vi': qa.get('question_vi', ''),
        'answer_vi': qa.get('answer_vi', ''),
        'qa_type': qa.get('qa_type', 'general'),  # general, visual, contextual, etc.
        'created_at': qa['created_at'].isoformat()
    } for qa in qa_pairs]

    return jsonify(result)


@images_bp.route('/<image_id>', methods=['PUT'])
@token_required
def update_image(image_id):
    data = request.get_json()
    
    try:
        image = current_app.db.images.find_one({'_id': ObjectId(image_id)})
    except Exception:
        return jsonify({'error': 'Invalid image ID'}), 400

    if not image:
        return jsonify({'error': 'Image not found'}), 404

    update_fields = {}
    allowed_fields = ['status', 'current_step', 'subpart_id', 'tags', 'annotators', 
                      'classification', 'review_status', 'review_comment', 'width', 'height',
                      'knowledge_base_ids']
    
    for field in allowed_fields:
        if field in data:
            if field == 'subpart_id' and data[field]:
                update_fields[field] = ObjectId(data[field])
            elif field == 'tags':
                update_fields[field] = [ObjectId(t) if not isinstance(t, ObjectId) else t for t in data[field]]
            elif field == 'annotators':
                update_fields[field] = [ObjectId(a) for a in data[field]]
            else:
                update_fields[field] = data[field]

    update_fields['updated_at'] = datetime.now(timezone.utc)

    current_app.db.images.update_one(
        {'_id': ObjectId(image_id)},
        {'$set': update_fields}
    )

    updated = current_app.db.images.find_one({'_id': ObjectId(image_id)})
    return jsonify(_build_image_stats(current_app.db, updated))


@images_bp.route('/<image_id>', methods=['DELETE'])
@token_required
def delete_image(image_id):
    try:
        image = current_app.db.images.find_one({'_id': ObjectId(image_id)})
    except Exception:
        return jsonify({'error': 'Invalid image ID'}), 400

    if not image:
        return jsonify({'error': 'Image not found'}), 404

    # Delete related data
    current_app.db.image_regions.delete_many({'image_id': ObjectId(image_id)})
    current_app.db.image_captions.delete_many({'image_id': ObjectId(image_id)})
    current_app.db.image_qa.delete_many({'image_id': ObjectId(image_id)})

    # Delete file
    try:
        if os.path.exists(image['file_path']):
            os.remove(image['file_path'])
    except Exception:
        pass

    current_app.db.images.delete_one({'_id': ObjectId(image_id)})

    return jsonify({'message': 'Image deleted successfully'})


# ============ IMAGE REGIONS (Segmentation/Detection) ============

@images_bp.route('/<image_id>/regions', methods=['GET'])
@token_required
def get_image_regions(image_id):
    try:
        regions = list(current_app.db.image_regions.find({'image_id': ObjectId(image_id)}))
    except Exception:
        return jsonify({'error': 'Invalid image ID'}), 400

    result = []
    for r in regions:
        region_data = {
            'id': str(r['_id']),
            'image_id': str(r['image_id']),
            'label': r.get('label', ''),
            'color': r.get('color', '#FF0000'),
            'category_id': str(r['category_id']) if r.get('category_id') else None,
            'bbox': r.get('bbox'),
            'segmentation_mask': r.get('segmentation_mask', ''),
            'brush_mask': r.get('brush_mask', ''),
            'knowledge_base_ids': r.get('knowledge_base_ids', []),
            'indexed': bool(r.get('indexed', False)),
            'indexed_at': r['indexed_at'].isoformat() if r.get('indexed_at') else None,
            'created_at': r['created_at'].isoformat()
        }
        # Check if region has caption
        caption = current_app.db.image_captions.find_one({'region_id': r['_id']})
        region_data['has_caption'] = caption is not None
        result.append(region_data)

    return jsonify(result)


@images_bp.route('/<image_id>/regions', methods=['POST'])
@token_required
def create_image_region(image_id):
    data = request.get_json()
    
    try:
        image = current_app.db.images.find_one({'_id': ObjectId(image_id)})
    except Exception:
        return jsonify({'error': 'Invalid image ID'}), 400

    if not image:
        return jsonify({'error': 'Image not found'}), 404

    region = {
        'image_id': ObjectId(image_id),
        'label': data.get('label', 'Object'),
        'color': data.get('color', '#FF0000'),
        'category_id': ObjectId(data['category_id']) if data.get('category_id') else None,
        'bbox': data.get('bbox'),  # [x, y, width, height]
        'segmentation_mask': data.get('segmentation_mask', ''),
        'brush_mask': data.get('brush_mask', ''),
        'knowledge_base_ids': data.get('knowledge_base_ids', []),
        'indexed': False,
        'created_at': datetime.now(timezone.utc)
    }

    result = current_app.db.image_regions.insert_one(region)
    
    # Reset review if approved
    _reset_image_approval_if_needed(ObjectId(image_id))
    current_app.db.images.update_one(
        {'_id': ObjectId(image_id)},
        {'$set': {'indexed': False, 'indexed_regions': 0, 'updated_at': datetime.now(timezone.utc)}}
    )

    return jsonify({
        'id': str(result.inserted_id),
        'image_id': image_id,
        'label': region['label'],
        'color': region['color'],
        'category_id': str(region['category_id']) if region['category_id'] else None,
        'bbox': region['bbox'],
        'segmentation_mask': region['segmentation_mask'],
        'brush_mask': region['brush_mask'],
        'knowledge_base_ids': region['knowledge_base_ids'],
        'indexed': False,
        'indexed_at': None,
        'created_at': region['created_at'].isoformat()
    }), 201


@images_bp.route('/regions/<region_id>', methods=['PUT'])
@token_required
def update_image_region(region_id):
    data = request.get_json()
    
    try:
        region = current_app.db.image_regions.find_one({'_id': ObjectId(region_id)})
    except Exception:
        return jsonify({'error': 'Invalid region ID'}), 400

    if not region:
        return jsonify({'error': 'Region not found'}), 404

    update_fields = {}
    allowed_fields = ['label', 'color', 'category_id', 'bbox', 'segmentation_mask', 'brush_mask', 'knowledge_base_ids']
    
    for field in allowed_fields:
        if field in data:
            if field == 'category_id' and data[field]:
                update_fields[field] = ObjectId(data[field])
            else:
                update_fields[field] = data[field]

    current_app.db.image_regions.update_one(
        {'_id': ObjectId(region_id)},
        {'$set': {**update_fields, 'indexed': False}}
    )

    # Reset review if approved
    _reset_image_approval_if_needed(region['image_id'])
    current_app.db.images.update_one(
        {'_id': region['image_id']},
        {'$set': {'indexed': False, 'indexed_regions': 0, 'updated_at': datetime.now(timezone.utc)}}
    )

    updated = current_app.db.image_regions.find_one({'_id': ObjectId(region_id)})
    return jsonify({
        'id': str(updated['_id']),
        'image_id': str(updated['image_id']),
        'label': updated.get('label', ''),
        'color': updated.get('color', '#FF0000'),
        'category_id': str(updated['category_id']) if updated.get('category_id') else None,
        'bbox': updated.get('bbox'),
        'segmentation_mask': updated.get('segmentation_mask', ''),
        'brush_mask': updated.get('brush_mask', ''),
        'knowledge_base_ids': updated.get('knowledge_base_ids', []),
        'indexed': bool(updated.get('indexed', False)),
        'indexed_at': updated['indexed_at'].isoformat() if updated.get('indexed_at') else None,
        'created_at': updated['created_at'].isoformat()
    })


@images_bp.route('/regions/<region_id>', methods=['DELETE'])
@token_required
def delete_image_region(region_id):
    try:
        region = current_app.db.image_regions.find_one({'_id': ObjectId(region_id)})
    except Exception:
        return jsonify({'error': 'Invalid region ID'}), 400

    if not region:
        return jsonify({'error': 'Region not found'}), 404

    # Delete region caption
    current_app.db.image_captions.delete_many({'region_id': ObjectId(region_id)})
    
    # Delete region
    current_app.db.image_regions.delete_one({'_id': ObjectId(region_id)})
    
    # Reset review if approved
    _reset_image_approval_if_needed(region['image_id'])
    current_app.db.images.update_one(
        {'_id': region['image_id']},
        {'$set': {'indexed': False, 'indexed_regions': 0, 'updated_at': datetime.now(timezone.utc)}}
    )

    return jsonify({'message': 'Region deleted successfully'})


# ============ IMAGE CAPTIONS ============

@images_bp.route('/<image_id>/caption', methods=['GET'])
@token_required
def get_image_caption(image_id):
    """Get image-level caption."""
    try:
        caption = current_app.db.image_captions.find_one({
            'image_id': ObjectId(image_id),
            'region_id': None
        })
    except Exception:
        return jsonify({'error': 'Invalid image ID'}), 400

    if not caption:
        return jsonify({
            'visual_caption': '',
            'contextual_caption': '',
            'knowledge_caption': '',
            'combined_caption': '',
            'visual_caption_vi': '',
            'contextual_caption_vi': '',
            'knowledge_caption_vi': '',
            'combined_caption_vi': '',
            'knowledge_base_ids': []
        })

    return jsonify({
        'id': str(caption['_id']),
        'visual_caption': caption.get('visual_caption', ''),
        'contextual_caption': caption.get('contextual_caption', ''),
        'knowledge_caption': caption.get('knowledge_caption', ''),
        'combined_caption': caption.get('combined_caption', ''),
        'visual_caption_vi': caption.get('visual_caption_vi', ''),
        'contextual_caption_vi': caption.get('contextual_caption_vi', ''),
        'knowledge_caption_vi': caption.get('knowledge_caption_vi', ''),
        'combined_caption_vi': caption.get('combined_caption_vi', ''),
        'knowledge_base_ids': _serialize_object_id_list(caption.get('knowledge_base_ids', []))
    })


@images_bp.route('/<image_id>/caption', methods=['POST'])
@token_required
def save_image_caption(image_id):
    """Save or update image-level caption."""
    data = request.get_json()
    
    try:
        image = current_app.db.images.find_one({'_id': ObjectId(image_id)})
    except Exception:
        return jsonify({'error': 'Invalid image ID'}), 400

    if not image:
        return jsonify({'error': 'Image not found'}), 404

    caption_fields = {
        'visual_caption': data.get('visual_caption', ''),
        'contextual_caption': data.get('contextual_caption', ''),
        'knowledge_caption': data.get('knowledge_caption', ''),
        'combined_caption': data.get('combined_caption', ''),
        'visual_caption_vi': data.get('visual_caption_vi', ''),
        'contextual_caption_vi': data.get('contextual_caption_vi', ''),
        'knowledge_caption_vi': data.get('knowledge_caption_vi', ''),
        'combined_caption_vi': data.get('combined_caption_vi', ''),
        'knowledge_base_ids': [ObjectId(kb_id) for kb_id in data.get('knowledge_base_ids', [])],
        'updated_at': datetime.now(timezone.utc)
    }

    # Upsert caption
    existing = current_app.db.image_captions.find_one({
        'image_id': ObjectId(image_id),
        'region_id': None
    })

    if existing:
        current_app.db.image_captions.update_one(
            {'_id': existing['_id']},
            {'$set': caption_fields}
        )
        caption_id = existing['_id']
    else:
        caption_fields['image_id'] = ObjectId(image_id)
        caption_fields['region_id'] = None
        caption_fields['created_at'] = datetime.now(timezone.utc)
        result = current_app.db.image_captions.insert_one(caption_fields)
        caption_id = result.inserted_id

    # Reset review if approved
    _reset_image_approval_if_needed(ObjectId(image_id))

    return jsonify({
        'id': str(caption_id),
        'message': 'Caption saved successfully'
    })


@images_bp.route('/regions/<region_id>/caption', methods=['GET'])
@token_required
def get_region_caption(region_id):
    """Get region-level caption."""
    try:
        caption = current_app.db.image_captions.find_one({'region_id': ObjectId(region_id)})
    except Exception:
        return jsonify({'error': 'Invalid region ID'}), 400

    if not caption:
        return jsonify({
            'visual_caption': '',
            'contextual_caption': '',
            'knowledge_caption': '',
            'combined_caption': '',
            'visual_caption_vi': '',
            'contextual_caption_vi': '',
            'knowledge_caption_vi': '',
            'combined_caption_vi': '',
            'knowledge_base_ids': []
        })

    return jsonify({
        'id': str(caption['_id']),
        'visual_caption': caption.get('visual_caption', ''),
        'contextual_caption': caption.get('contextual_caption', ''),
        'knowledge_caption': caption.get('knowledge_caption', ''),
        'combined_caption': caption.get('combined_caption', ''),
        'visual_caption_vi': caption.get('visual_caption_vi', ''),
        'contextual_caption_vi': caption.get('contextual_caption_vi', ''),
        'knowledge_caption_vi': caption.get('knowledge_caption_vi', ''),
        'combined_caption_vi': caption.get('combined_caption_vi', ''),
        'knowledge_base_ids': _serialize_object_id_list(caption.get('knowledge_base_ids', []))
    })


@images_bp.route('/regions/<region_id>/caption', methods=['POST'])
@token_required
def save_region_caption(region_id):
    """Save or update region-level caption."""
    data = request.get_json()
    
    try:
        region = current_app.db.image_regions.find_one({'_id': ObjectId(region_id)})
    except Exception:
        return jsonify({'error': 'Invalid region ID'}), 400

    if not region:
        return jsonify({'error': 'Region not found'}), 404

    caption_fields = {
        'visual_caption': data.get('visual_caption', ''),
        'contextual_caption': data.get('contextual_caption', ''),
        'knowledge_caption': data.get('knowledge_caption', ''),
        'combined_caption': data.get('combined_caption', ''),
        'visual_caption_vi': data.get('visual_caption_vi', ''),
        'contextual_caption_vi': data.get('contextual_caption_vi', ''),
        'knowledge_caption_vi': data.get('knowledge_caption_vi', ''),
        'combined_caption_vi': data.get('combined_caption_vi', ''),
        'knowledge_base_ids': [ObjectId(kb_id) for kb_id in data.get('knowledge_base_ids', [])],
        'updated_at': datetime.now(timezone.utc)
    }

    # Upsert caption
    existing = current_app.db.image_captions.find_one({'region_id': ObjectId(region_id)})

    if existing:
        current_app.db.image_captions.update_one(
            {'_id': existing['_id']},
            {'$set': caption_fields}
        )
        caption_id = existing['_id']
    else:
        caption_fields['image_id'] = region['image_id']
        caption_fields['region_id'] = ObjectId(region_id)
        caption_fields['created_at'] = datetime.now(timezone.utc)
        result = current_app.db.image_captions.insert_one(caption_fields)
        caption_id = result.inserted_id

    # Reset review if approved
    _reset_image_approval_if_needed(region['image_id'])

    return jsonify({
        'id': str(caption_id),
        'message': 'Caption saved successfully'
    })


# ============ IMAGE QA (Question & Answer) ============

@images_bp.route('/<image_id>/qa', methods=['GET'])
@token_required
def get_image_qa(image_id):
    """Get all QA pairs for an image."""
    try:
        qa_pairs = list(current_app.db.image_qa.find({'image_id': ObjectId(image_id)}))
    except Exception:
        return jsonify({'error': 'Invalid image ID'}), 400

    return jsonify([{
        'id': str(qa['_id']),
        'question': qa.get('question', ''),
        'answer': qa.get('answer', ''),
        'question_vi': qa.get('question_vi', ''),
        'answer_vi': qa.get('answer_vi', ''),
        'qa_type': qa.get('qa_type', 'general'),
        'created_at': qa['created_at'].isoformat()
    } for qa in qa_pairs])


@images_bp.route('/<image_id>/qa', methods=['POST'])
@token_required
def create_image_qa(image_id):
    """Create a new QA pair for an image."""
    data = request.get_json()
    
    try:
        image = current_app.db.images.find_one({'_id': ObjectId(image_id)})
    except Exception:
        return jsonify({'error': 'Invalid image ID'}), 400

    if not image:
        return jsonify({'error': 'Image not found'}), 404

    qa_doc = {
        'image_id': ObjectId(image_id),
        'question': data.get('question', ''),
        'answer': data.get('answer', ''),
        'question_vi': data.get('question_vi', ''),
        'answer_vi': data.get('answer_vi', ''),
        'qa_type': data.get('qa_type', 'general'),
        'created_at': datetime.now(timezone.utc),
        'updated_at': datetime.now(timezone.utc)
    }

    result = current_app.db.image_qa.insert_one(qa_doc)
    
    # Reset review if approved
    _reset_image_approval_if_needed(ObjectId(image_id))

    return jsonify({
        'id': str(result.inserted_id),
        'question': qa_doc['question'],
        'answer': qa_doc['answer'],
        'question_vi': qa_doc['question_vi'],
        'answer_vi': qa_doc['answer_vi'],
        'qa_type': qa_doc['qa_type'],
        'created_at': qa_doc['created_at'].isoformat()
    }), 201


@images_bp.route('/qa/<qa_id>', methods=['PUT'])
@token_required
def update_image_qa(qa_id):
    """Update a QA pair."""
    data = request.get_json()
    
    try:
        qa = current_app.db.image_qa.find_one({'_id': ObjectId(qa_id)})
    except Exception:
        return jsonify({'error': 'Invalid QA ID'}), 400

    if not qa:
        return jsonify({'error': 'QA pair not found'}), 404

    update_fields = {
        'updated_at': datetime.now(timezone.utc)
    }
    
    allowed_fields = ['question', 'answer', 'question_vi', 'answer_vi', 'qa_type']
    for field in allowed_fields:
        if field in data:
            update_fields[field] = data[field]

    current_app.db.image_qa.update_one(
        {'_id': ObjectId(qa_id)},
        {'$set': update_fields}
    )

    # Reset review if approved
    _reset_image_approval_if_needed(qa['image_id'])

    updated = current_app.db.image_qa.find_one({'_id': ObjectId(qa_id)})
    return jsonify({
        'id': str(updated['_id']),
        'question': updated.get('question', ''),
        'answer': updated.get('answer', ''),
        'question_vi': updated.get('question_vi', ''),
        'answer_vi': updated.get('answer_vi', ''),
        'qa_type': updated.get('qa_type', 'general'),
        'created_at': updated['created_at'].isoformat()
    })


@images_bp.route('/qa/<qa_id>', methods=['DELETE'])
@token_required
def delete_image_qa(qa_id):
    """Delete a QA pair."""
    try:
        qa = current_app.db.image_qa.find_one({'_id': ObjectId(qa_id)})
    except Exception:
        return jsonify({'error': 'Invalid QA ID'}), 400

    if not qa:
        return jsonify({'error': 'QA pair not found'}), 404

    current_app.db.image_qa.delete_one({'_id': ObjectId(qa_id)})
    
    # Reset review if approved
    _reset_image_approval_if_needed(qa['image_id'])

    return jsonify({'message': 'QA pair deleted successfully'})


# ============ IMAGE CLASSIFICATION ============

@images_bp.route('/<image_id>/classification', methods=['POST'])
@token_required
def set_image_classification(image_id):
    """Set classification for an image."""
    data = request.get_json()
    
    try:
        image = current_app.db.images.find_one({'_id': ObjectId(image_id)})
    except Exception:
        return jsonify({'error': 'Invalid image ID'}), 400

    if not image:
        return jsonify({'error': 'Image not found'}), 404

    classification = {
        'labels': data.get('labels', []),  # List of classification labels
        'primary_label': data.get('primary_label', ''),
        'confidence': data.get('confidence'),
        'notes': data.get('notes', '')
    }

    current_app.db.images.update_one(
        {'_id': ObjectId(image_id)},
        {'$set': {
            'classification': classification,
            'updated_at': datetime.now(timezone.utc)
        }}
    )

    # Reset review if approved
    _reset_image_approval_if_needed(ObjectId(image_id))

    return jsonify({
        'message': 'Classification saved successfully',
        'classification': classification
    })


# ============ AI SEGMENTATION ============

@images_bp.route('/segment-object', methods=['POST'])
@token_required
def segment_image_object():
    """Send brush mask to SAM2/DAM for AI segmentation."""
    import requests as http_requests
    import base64
    
    data = request.get_json()
    brush_mask = data.get('brush_mask')
    image_data = data.get('image_data')

    if not brush_mask:
        return jsonify({'error': 'brush_mask is required'}), 400

    # Get DAM server URL
    from routes.settings import get_dam_url
    dam_url = get_dam_url()
    if not dam_url:
        return jsonify({'error': 'DAM server URL not configured'}), 400

    try:
        # Call DAM server for segmentation
        response = http_requests.post(
            f"{dam_url}/segment",
            json={
                'brush_mask': brush_mask,
                'frame_image': image_data
            },
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            return jsonify({
                'segmented_mask': result.get('segmented_mask', ''),
                'confidence': result.get('confidence', 0),
                'message': 'Segmentation completed'
            })
        else:
            return jsonify({'error': f'DAM server error: {response.status_code}'}), 500
            
    except http_requests.exceptions.Timeout:
        return jsonify({'error': 'DAM server timeout'}), 504
    except http_requests.exceptions.ConnectionError:
        return jsonify({'error': 'Cannot connect to DAM server'}), 503
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ REVIEW STATUS ============

@images_bp.route('/<image_id>/review', methods=['POST'])
@token_required
def submit_image_for_review(image_id):
    """Submit image for review."""
    try:
        image = current_app.db.images.find_one({'_id': ObjectId(image_id)})
    except Exception:
        return jsonify({'error': 'Invalid image ID'}), 400

    if not image:
        return jsonify({'error': 'Image not found'}), 404

    current_app.db.images.update_one(
        {'_id': ObjectId(image_id)},
        {'$set': {
            'review_status': 'pending',
            'updated_at': datetime.now(timezone.utc)
        }}
    )

    return jsonify({'message': 'Image submitted for review'})


@images_bp.route('/<image_id>/review/<action>', methods=['POST'])
@token_required
def review_image(image_id, action):
    """Approve or reject an image."""
    if action not in ['approve', 'reject']:
        return jsonify({'error': 'Invalid action'}), 400

    data = request.get_json() or {}
    
    try:
        image = current_app.db.images.find_one({'_id': ObjectId(image_id)})
    except Exception:
        return jsonify({'error': 'Invalid image ID'}), 400

    if not image:
        return jsonify({'error': 'Image not found'}), 404

    review_entry = {
        'reviewer_id': request.current_user['_id'],
        'action': action,
        'comment': data.get('comment', ''),
        'reviewed_at': datetime.now(timezone.utc)
    }

    # Add to reviews array
    reviews = image.get('reviews', [])
    reviews.append(review_entry)

    update_data = {
        'reviews': reviews,
        'review_status': 'approved' if action == 'approve' else 'rejected',
        'reviewed_by': request.current_user['_id'],
        'review_comment': data.get('comment', ''),
        'updated_at': datetime.now(timezone.utc)
    }

    current_app.db.images.update_one(
        {'_id': ObjectId(image_id)},
        {'$set': update_data}
    )

    return jsonify({'message': f'Image {action}d successfully'})


# ============ QC STATS ============

@images_bp.route('/qc-stats', methods=['GET'])
@token_required
def get_image_qc_stats():
    """Get QC statistics for images."""
    db = current_app.db
    
    # Get all images
    images = list(db.images.find())
    
    stats = {
        'total_images': len(images),
        'by_status': {
            'pending': 0,
            'approved': 0,
            'rejected': 0,
            'not_submitted': 0
        },
        'by_project': {},
        'by_user': [],
        'recent_reviews': [],
        'pending_reviews': []
    }

    # Count by review status
    for img in images:
        status = img.get('review_status', 'not_submitted')
        if status in stats['by_status']:
            stats['by_status'][status] += 1
        else:
            stats['by_status']['not_submitted'] += 1

    # Group by project
    projects = {str(p['_id']): p['name'] for p in db.projects.find()}
    for img in images:
        proj_id = str(img.get('project_id', ''))
        proj_name = projects.get(proj_id, 'Unknown')
        if proj_name not in stats['by_project']:
            stats['by_project'][proj_name] = {
                'total': 0, 'approved': 0, 'rejected': 0, 'pending': 0
            }
        stats['by_project'][proj_name]['total'] += 1
        status = img.get('review_status', 'not_submitted')
        if status in ['approved', 'rejected', 'pending']:
            stats['by_project'][proj_name][status] += 1

    # Get recent reviews
    reviewed_images = [img for img in images if img.get('reviews')]
    reviewed_images.sort(key=lambda x: x.get('reviews', [{}])[-1].get('reviewed_at', datetime.min), reverse=True)
    
    for img in reviewed_images[:20]:
        if img.get('reviews'):
            last_review = img['reviews'][-1]
            reviewer = db.users.find_one({'_id': last_review['reviewer_id']})
            stats['recent_reviews'].append({
                'image_id': str(img['_id']),
                'image_name': img['original_name'],
                'project_name': projects.get(str(img.get('project_id', '')), 'Unknown'),
                'reviewer_name': reviewer.get('full_name', reviewer.get('username', 'Unknown')) if reviewer else 'Unknown',
                'reviewer_color': reviewer.get('avatar_color', '#888') if reviewer else '#888',
                'status': last_review['action'],
                'reviewed_at': last_review['reviewed_at'].isoformat()
            })

    # Get pending reviews
    pending_images = [img for img in images if img.get('review_status') == 'pending']
    for img in pending_images[:20]:
        stats['pending_reviews'].append({
            'image_id': str(img['_id']),
            'image_name': img['original_name'],
            'project_name': projects.get(str(img.get('project_id', '')), 'Unknown'),
            'created_at': img['created_at'].isoformat()
        })

    return jsonify(stats)


# ============ EXPORT ============

@images_bp.route('/export/<image_id>', methods=['GET'])
@token_required
def export_image_annotations(image_id):
    """Export all annotations for a single image."""
    try:
        image = current_app.db.images.find_one({'_id': ObjectId(image_id)})
    except Exception:
        return jsonify({'error': 'Invalid image ID'}), 400

    if not image:
        return jsonify({'error': 'Image not found'}), 404

    # Get project info
    project = current_app.db.projects.find_one({'_id': image['project_id']})

    # Build export data
    export_data = {
        'dataset_info': {
            'format': 'image_annotation_v1',
            'export_date': datetime.now(timezone.utc).isoformat(),
            'total_images': 1
        },
        'image': {
            'id': str(image['_id']),
            'filename': image['original_name'],
            'width': image.get('width', 0),
            'height': image.get('height', 0),
            'classification': image.get('classification'),
            'regions': [],
            'image_caption': None,
            'qa_pairs': []
        }
    }

    if project:
        export_data['dataset_info']['project_name'] = project['name']

    # Get regions with captions
    regions = list(current_app.db.image_regions.find({'image_id': ObjectId(image_id)}))
    for r in regions:
        region_data = {
            'id': str(r['_id']),
            'label': r.get('label', ''),
            'bbox': r.get('bbox'),
            'segmentation_mask': r.get('segmentation_mask', ''),
            'captions': None
        }
        
        caption = current_app.db.image_captions.find_one({'region_id': r['_id']})
        if caption:
            region_data['captions'] = {
                'en': {
                    'visual': caption.get('visual_caption', ''),
                    'contextual': caption.get('contextual_caption', ''),
                    'knowledge': caption.get('knowledge_caption', ''),
                    'combined': caption.get('combined_caption', '')
                },
                'vi': {
                    'visual': caption.get('visual_caption_vi', ''),
                    'contextual': caption.get('contextual_caption_vi', ''),
                    'knowledge': caption.get('knowledge_caption_vi', ''),
                    'combined': caption.get('combined_caption_vi', '')
                }
            }
        
        export_data['image']['regions'].append(region_data)

    # Get image-level caption
    img_caption = current_app.db.image_captions.find_one({
        'image_id': ObjectId(image_id),
        'region_id': None
    })
    if img_caption:
        export_data['image']['image_caption'] = {
            'en': {
                'visual': img_caption.get('visual_caption', ''),
                'contextual': img_caption.get('contextual_caption', ''),
                'knowledge': img_caption.get('knowledge_caption', ''),
                'combined': img_caption.get('combined_caption', '')
            },
            'vi': {
                'visual': img_caption.get('visual_caption_vi', ''),
                'contextual': img_caption.get('contextual_caption_vi', ''),
                'knowledge': img_caption.get('knowledge_caption_vi', ''),
                'combined': img_caption.get('combined_caption_vi', '')
            }
        }

    # Get QA pairs
    qa_pairs = list(current_app.db.image_qa.find({'image_id': ObjectId(image_id)}))
    export_data['image']['qa_pairs'] = [{
        'question': qa.get('question', ''),
        'answer': qa.get('answer', ''),
        'question_vi': qa.get('question_vi', ''),
        'answer_vi': qa.get('answer_vi', ''),
        'qa_type': qa.get('qa_type', 'general')
    } for qa in qa_pairs]

    return jsonify(export_data)


def _reset_image_approval_if_needed(image_id):
    """Reset image review status if it was approved (content changed)."""
    image = current_app.db.images.find_one({'_id': image_id})
    if image and image.get('review_status') == 'approved':
        current_app.db.images.update_one(
            {'_id': image_id},
            {'$set': {
                'review_status': 'not_submitted',
                'reviews': [],
                'review_comment': 'Auto-reset: Content modified after approval',
                'updated_at': datetime.now(timezone.utc)
            }}
        )


# ============ Image Indexing with DINOv2 ============

@images_bp.route('/<image_id>/index', methods=['POST'])
@token_required
def index_image(image_id):
    """
    Index an image and its regions using DINOv2 embeddings.
    """
    try:
        image = current_app.db.images.find_one({'_id': ObjectId(image_id)})
    except Exception:
        return jsonify({'error': 'Invalid image ID'}), 400

    if not image:
        return jsonify({'error': 'Image not found'}), 404

    try:
        # Read image file
        image_path = os.path.join(Config.UPLOAD_FOLDER, 'images', image['filename'])
        if not os.path.exists(image_path):
            return jsonify({'error': 'Image file not found'}), 404
        
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        image_base64 = f"data:image/jpeg;base64,{base64.b64encode(image_bytes).decode('utf-8')}"
        
        indexed_count = 0
        indexed_regions_count = 0
        
        # Get embedding from DAM server and persist in backend vector store.
        response = requests.post(
            f"{Config.DAM_SERVER_URL}/embed",
            json={'image': image_base64, 'entity_id': str(image_id), 'entity_type': 'image'},
            timeout=60,
        )
        if response.status_code != 200:
            return jsonify({'error': f'Embedding failed: {response.text}'}), 500
        emb = response.json().get('embedding')
        if emb:
            upsert_embedding(
                current_app.db,
                str(image_id),
                'image',
                emb,
                {
                    'filename': image['filename'],
                    'original_name': image['original_name'],
                    'project_id': str(image.get('project_id', '')),
                },
            )
            indexed_count += 1
        
        # Index each region
        regions = list(current_app.db.image_regions.find({'image_id': ObjectId(image_id)}))
        current_app.db.image_regions.update_many(
            {'image_id': ObjectId(image_id)},
            {'$set': {'indexed': False}}
        )
        for region in regions:
            # Create mask for region
            img = PILImage.open(BytesIO(image_bytes)).convert('RGB')
            width, height = img.size
            
            # Create mask
            mask = np.zeros((height, width), dtype=np.uint8)
            points = region.get('points', [])
            if points:
                pts = np.array([[int(p['x'] * width), int(p['y'] * height)] for p in points], np.int32)
                cv2.fillPoly(mask, [pts], 255)
            
            # Convert mask to base64
            mask_pil = PILImage.fromarray(mask)
            mask_buffer = BytesIO()
            mask_pil.save(mask_buffer, format='PNG')
            mask_base64 = f"data:image/png;base64,{base64.b64encode(mask_buffer.getvalue()).decode('utf-8')}"
            
            response = requests.post(
                f"{Config.DAM_SERVER_URL}/embed",
                json={
                    'image': image_base64,
                    'mask': mask_base64,
                    'entity_id': str(region['_id']),
                    'entity_type': 'object',
                },
                timeout=60,
            )
            if response.status_code != 200:
                continue

            emb = response.json().get('embedding')
            if emb:
                upsert_embedding(
                    current_app.db,
                    str(region['_id']),
                    'object',
                    emb,
                    {
                        'image_id': str(image_id),
                        'label': region.get('label', ''),
                        'color': region.get('color', ''),
                    },
                )
                indexed_count += 1
                indexed_regions_count += 1
                current_app.db.image_regions.update_one(
                    {'_id': region['_id']},
                    {'$set': {'indexed': True, 'indexed_at': datetime.now(timezone.utc)}}
                )
        
        # Update image with indexing info
        current_app.db.images.update_one(
            {'_id': ObjectId(image_id)},
            {
                '$set': {
                    'indexed': True,
                    'indexed_regions': indexed_regions_count,
                    'indexed_at': datetime.now(timezone.utc),
                    'updated_at': datetime.now(timezone.utc)
                }
            }
        )
        
        return jsonify({
            'success': True,
            'indexed_count': indexed_count,
            'indexed_regions': indexed_regions_count,
            'image_id': image_id
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@images_bp.route('/search', methods=['POST'])
@token_required
def search_images_by_image():
    """
    Search for similar images/regions using an image query.
    """
    data = request.get_json()
    if not data or not data.get('query_image'):
        return jsonify({'error': 'query_image required'}), 400
    
    try:
        response = requests.post(
            f"{Config.DAM_SERVER_URL}/embed",
            json={
                'image': data['query_image'],
                'mask': data.get('query_mask'),
            },
            timeout=60
        )
        if response.status_code != 200:
            return jsonify({'error': f'Embedding failed: {response.text}'}), 500

        query_embedding = response.json().get('embedding')
        if not query_embedding:
            return jsonify({'results': [], 'total': 0})

        search_results = {
            'results': search_embeddings(
                current_app.db,
                query_embedding,
                top_k=data.get('top_k', 20),
                entity_types=data.get('entity_types', ['image', 'object']),
            )
        }
        
        # Enrich results with image details
        enriched_results = []
        for result in search_results.get('results', []):
            entity_id = result.get('entity_id')
            entity_type = result.get('entity_type')
            
            try:
                if entity_type == 'image':
                    image = current_app.db.images.find_one({'_id': ObjectId(entity_id)})
                    if image:
                        enriched_results.append({
                            'entity_type': 'image',
                            'score': result['score'],
                            'image': _build_image_stats(current_app.db, image)
                        })
                elif entity_type == 'object':
                    region = current_app.db.image_regions.find_one({'_id': ObjectId(entity_id)})
                    if region:
                        image = current_app.db.images.find_one({'_id': region['image_id']})
                        enriched_results.append({
                            'entity_type': 'object',
                            'score': result['score'],
                            'region': {
                                'id': str(region['_id']),
                                'label': region.get('label', ''),
                                'color': region.get('color', ''),
                                'points': region.get('points', [])
                            },
                            'image': _build_image_stats(current_app.db, image) if image else None
                        })
            except Exception:
                pass
        
        return jsonify({
            'results': enriched_results,
            'total': len(enriched_results)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@images_bp.route('/index/batch', methods=['POST'])
@token_required  
def batch_index_images():
    """
    Batch index multiple images and their regions.
    """
    data = request.get_json() or {}
    image_ids = data.get('image_ids', [])
    
    if not image_ids:
        return jsonify({'error': 'image_ids required'}), 400
    
    results = []
    for image_id in image_ids:
        try:
            # index_image can return Response or (Response, status).
            raw_response = index_image(image_id)

            status_code = 200
            response_obj = raw_response
            if isinstance(raw_response, tuple):
                response_obj = raw_response[0]
                if len(raw_response) > 1 and isinstance(raw_response[1], int):
                    status_code = raw_response[1]

            if hasattr(response_obj, 'get_json'):
                response_data = response_obj.get_json(silent=True) or {}
                status_code = getattr(response_obj, 'status_code', status_code)
            elif isinstance(response_obj, dict):
                response_data = response_obj
            else:
                response_data = {'message': str(response_obj)}

            success = 200 <= status_code < 300 and response_data.get('success', True)
            results.append({
                'image_id': image_id,
                'success': bool(success),
                'status_code': status_code,
                'data': response_data,
                'error': response_data.get('error') if not success and isinstance(response_data, dict) else None,
            })
        except Exception as e:
            results.append({
                'image_id': image_id,
                'success': False,
                'error': str(e)
            })
    
    return jsonify({
        'results': results,
        'total': len(results),
        'success_count': sum(1 for r in results if r.get('success'))
    })
