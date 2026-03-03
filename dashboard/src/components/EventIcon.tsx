import {
  AlertTriangle,
  Check,
  XCircle,
  Megaphone,
  ShieldAlert,
  CheckCircle,
  TrendingDown,
  Heart,
  HelpCircle,
  Thermometer,
  Brain,
  Apple,
  ShieldBan,
  Smile,
  Droplets,
  Footprints,
  Moon,
  Wind,
} from 'lucide-react';
import type { EventType } from '../types';

interface EventIconProps {
  eventType: EventType;
  className?: string;
  size?: number;
}

const EVENT_ICON_MAP: Record<
  EventType,
  { icon: React.ElementType; color: string }
> = {
  fall_detected: { icon: AlertTriangle, color: 'text-red-500' },
  medication_taken: { icon: Check, color: 'text-green-500' },
  medication_missed: { icon: XCircle, color: 'text-orange-500' },
  medication_late: { icon: XCircle, color: 'text-yellow-500' },
  acoustic_scream: { icon: Megaphone, color: 'text-red-400' },
  acoustic_glass_break: { icon: ShieldAlert, color: 'text-red-600' },
  acoustic_impact: { icon: ShieldAlert, color: 'text-orange-400' },
  acoustic_silence: { icon: ShieldAlert, color: 'text-gray-400' },
  check_in_completed: { icon: CheckCircle, color: 'text-green-500' },
  routine_anomaly: { icon: TrendingDown, color: 'text-yellow-500' },
  vital_alert: { icon: Heart, color: 'text-rose-500' },
  environmental_alert: { icon: Thermometer, color: 'text-amber-500' },
  cognitive_decline: { icon: Brain, color: 'text-purple-500' },
  nutrition_concern: { icon: Apple, color: 'text-lime-600' },
  scam_alert: { icon: ShieldBan, color: 'text-red-600' },
  emotional_concern: { icon: Smile, color: 'text-blue-400' },
  bathroom_anomaly: { icon: Droplets, color: 'text-cyan-500' },
  choking: { icon: Wind, color: 'text-red-600' },
  gait_degradation: { icon: Footprints, color: 'text-orange-500' },
  sleep_disruption: { icon: Moon, color: 'text-indigo-400' },
};

export default function EventIcon({
  eventType,
  className = '',
  size = 18,
}: EventIconProps) {
  const config = EVENT_ICON_MAP[eventType] ?? {
    icon: HelpCircle,
    color: 'text-gray-400',
  };
  const Icon = config.icon;

  return <Icon className={`${config.color} ${className}`} size={size} />;
}
