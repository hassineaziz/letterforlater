/**
 * S3 Media Upload Handler for Legacy Letter Application
 * Handles direct S3 uploads using presigned URLs
 */

class S3MediaUploader {
    constructor() {
        this.uploadQueue = [];
        this.activeUploads = new Map();
    }

    /**
     * Upload a file directly to S3 using presigned URL
     * @param {File} file - The file to upload
     * @param {string} mediaType - Type of media (image, video, audio)
     * @param {number} letterId - Optional letter ID for direct attachment
     * @returns {Promise} Upload result
     */
    async uploadFile(file, mediaType = 'image', letterId = null) {
        try {
            // Step 1: Get presigned upload URL from backend
            const uploadUrlResponse = await this.getUploadUrl(file.name, mediaType, letterId);
            
            if (!uploadUrlResponse.success) {
                throw new Error(uploadUrlResponse.error);
            }

            const { media_id, upload_url, upload_fields, s3_key } = uploadUrlResponse;

            // Step 2: Upload file directly to S3
            const formData = new FormData();
            
            // Add all fields from presigned URL
            Object.keys(upload_fields).forEach(key => {
                formData.append(key, upload_fields[key]);
            });
            
            // Add the file with explicit content type
            // Note: We need to create a new File object with the correct MIME type
            const fileWithCorrectType = new File([file], file.name, { 
                type: file.type || (file.name.endsWith('.m4a') ? 'audio/mp4' : file.type)
            });
            formData.append('file', fileWithCorrectType);

            // Upload to S3
            const uploadResponse = await fetch(upload_url, {
                method: 'POST',
                body: formData
            });

            if (!uploadResponse.ok) {
                throw new Error(`S3 upload failed: ${uploadResponse.status}`);
            }

            // Step 3: Confirm upload with backend
            const confirmResponse = await this.confirmUpload(media_id, file.size);
            
            if (!confirmResponse.success) {
                throw new Error(confirmResponse.error);
            }

            return {
                success: true,
                media_id: media_id,
                file_name: file.name,
                file_type: mediaType,
                file_size: file.size,
                s3_key: s3_key
            };

        } catch (error) {
            console.error('S3 upload error:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Get presigned upload URL from backend
     */
    async getUploadUrl(filename, mediaType, letterId) {
        const response = await fetch('/upload-media-url', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify({
                filename: filename,
                media_type: mediaType,
                letter_id: letterId
            })
        });

        // Check if response is JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            if (response.status === 302 || response.url.includes('/login')) {
                throw new Error('Authentication required. Please log in to upload files.');
            }
            throw new Error(`Unexpected response format. Status: ${response.status}`);
        }

        return await response.json();
    }

    /**
     * Confirm successful upload with backend
     */
    async confirmUpload(mediaId, fileSize) {
        const response = await fetch('/confirm-upload', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify({
                media_id: mediaId,
                file_size: fileSize
            })
        });

        // Check if response is JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            if (response.status === 302 || response.url.includes('/login')) {
                throw new Error('Authentication required. Please log in to confirm uploads.');
            }
            throw new Error(`Unexpected response format. Status: ${response.status}`);
        }

        return await response.json();
    }

    /**
     * Get presigned download URL for a media file
     */
    async getDownloadUrl(mediaId) {
        const response = await fetch(`/media/${mediaId}/download`, {
            credentials: 'include'
        });

        return await response.json();
    }

    /**
     * Upload multiple files with progress tracking
     */
    async uploadMultipleFiles(files, mediaType = 'image', letterId = null, onProgress = null) {
        const results = [];
        const totalFiles = files.length;
        let completedFiles = 0;

        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            
            try {
                const result = await this.uploadFile(file, mediaType, letterId);
                results.push(result);
                
                completedFiles++;
                if (onProgress) {
                    onProgress({
                        completed: completedFiles,
                        total: totalFiles,
                        currentFile: file.name,
                        result: result
                    });
                }
            } catch (error) {
                const errorResult = {
                    success: false,
                    error: error.message,
                    file_name: file.name
                };
                results.push(errorResult);
                
                completedFiles++;
                if (onProgress) {
                    onProgress({
                        completed: completedFiles,
                        total: totalFiles,
                        currentFile: file.name,
                        result: errorResult
                    });
                }
            }
        }

        return results;
    }

    /**
     * Delete a media file
     */
    async deleteMedia(mediaId) {
        const response = await fetch(`/delete-media/${mediaId}`, {
            method: 'POST',
            credentials: 'include'
        });

        return await response.json();
    }
}

/**
 * Blog Image Upload Handler for TinyMCE integration
 */
class BlogImageUploader {
    constructor() {
        this.uploader = new S3MediaUploader();
    }

    /**
     * Upload image for blog post and return URL for TinyMCE
     */
    async uploadImage(file) {
        try {
            const result = await this.uploader.uploadFile(file, 'image');
            
            if (result.success) {
                // For blog images, we need to return a URL that TinyMCE can use
                // Since we're using S3, we'll return a proxy URL that generates presigned URLs
                return {
                    success: true,
                    url: `/media/${result.media_id}` // This will redirect to presigned URL
                };
            } else {
                return {
                    success: false,
                    error: result.error
                };
            }
        } catch (error) {
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Get presigned URL for blog image upload (for direct S3 upload)
     */
    async getUploadUrl(filename) {
        const response = await fetch('/admin/upload-image-url', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify({
                filename: filename
            })
        });

        // Check if response is JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            if (response.status === 302 || response.url.includes('/login')) {
                throw new Error('Authentication required. Please log in to upload blog images.');
            }
            throw new Error(`Unexpected response format. Status: ${response.status}`);
        }

        return await response.json();
    }
}

// Global instances
window.s3MediaUploader = new S3MediaUploader();
window.blogImageUploader = new BlogImageUploader();

/**
 * Utility functions for media handling
 */
window.MediaUtils = {
    /**
     * Get file type from filename
     */
    getFileType(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        const imageExts = ['jpg', 'jpeg', 'png', 'gif', 'webp'];
        const videoExts = ['mp4'];
        const audioExts = ['mp3', 'wav', 'm4a'];

        if (imageExts.includes(ext)) return 'image';
        if (videoExts.includes(ext)) return 'video';
        if (audioExts.includes(ext)) return 'audio';
        return 'unknown';
    },

    /**
     * Format file size for display
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    /**
     * Validate file before upload
     */
    validateFile(file, maxSize = 100 * 1024 * 1024) { // 100MB default
        const errors = [];

        if (file.size > maxSize) {
            errors.push(`File too large. Maximum size: ${this.formatFileSize(maxSize)}`);
        }

        const fileType = this.getFileType(file.name);
        if (fileType === 'unknown') {
            errors.push('Unsupported file type');
        }

        return {
            valid: errors.length === 0,
            errors: errors,
            fileType: fileType
        };
    }
};
