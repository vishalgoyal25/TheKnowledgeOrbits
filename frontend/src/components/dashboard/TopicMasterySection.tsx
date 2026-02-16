import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { TopicMastery } from '@/types/dashboard';
import { AlertTriangle, CheckCircle } from 'lucide-react';
import ProgressBar from '@/components/charts/ProgressBar';

interface Props {
    weak: TopicMastery[];
    strong: TopicMastery[];
}

export default function TopicMasterySection({ weak, strong }: Props) {
    return (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <AlertTriangle className="h-5 w-5 text-orange-600" />
                        Weak Topics
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {weak.length === 0 ? (
                        <p className="text-gray-500">No weak topics - great job!</p>
                    ) : (
                        <div className="space-y-4">
                            {weak.map(topic => (
                                <div key={topic.topic_id} className="flex flex-col gap-1">
                                    <div className="flex justify-between items-center">
                                        <span className="text-sm font-medium">{topic.topic_name}</span>
                                        <span className="text-sm font-semibold text-orange-600">
                                            {topic.mastery_score.toFixed(0)}%
                                        </span>
                                    </div>
                                    <ProgressBar
                                        value={topic.mastery_score}
                                        barClassName="bg-orange-600"
                                    />
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <CheckCircle className="h-5 w-5 text-green-600" />
                        Strong Topics
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {strong.length === 0 ? (
                        <p className="text-gray-500">Keep practicing to build mastery!</p>
                    ) : (
                        <div className="space-y-4">
                            {strong.map(topic => (
                                <div key={topic.topic_id} className="flex flex-col gap-1">
                                    <div className="flex justify-between items-center">
                                        <span className="text-sm font-medium">{topic.topic_name}</span>
                                        <span className="text-sm font-semibold text-green-600">
                                            {topic.mastery_score.toFixed(0)}%
                                        </span>
                                    </div>
                                    <ProgressBar
                                        value={topic.mastery_score}
                                        barClassName="bg-green-600"
                                    />
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
