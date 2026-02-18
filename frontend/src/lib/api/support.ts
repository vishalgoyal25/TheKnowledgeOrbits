import apiClient from './client';

export interface FeedbackData {
    name: string;
    email: string;
    phone?: string;
    city?: string;
    institution?: string;
    user_type: 'aspirant' | 'student_school' | 'student_college' | 'educator' | 'researcher' | 'other';
    message: string;
}

export const supportAPI = {
    submitFeedback: async (data: FeedbackData) => {
        const response = await apiClient.post('/support/feedback/', data);
        return response.data;
    },
};
