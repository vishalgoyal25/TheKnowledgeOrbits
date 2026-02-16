/**
 * Reset Password Page
 */

'use client';

import { useParams } from 'next/navigation';
import ResetPasswordForm from '@/components/auth/ResetPasswordForm';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';

export default function ResetPasswordPage() {
    const params = useParams();
    const token = params.token as string;

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-yellow-50 to-orange-100 p-4">
            <Card className="w-full max-w-md">
                <CardHeader className="space-y-1">
                    <CardTitle className="text-2xl font-bold text-center">
                        Reset Password
                    </CardTitle>
                    <CardDescription className="text-center">
                        Enter your new password
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <ResetPasswordForm token={token} />
                </CardContent>
            </Card>
        </div>
    );
}
