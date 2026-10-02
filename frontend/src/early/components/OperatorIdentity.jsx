import { Link } from '../lib/router';
import { ArrowRight, LoaderCircle, UserRound } from 'lucide-react';
import { useXAvatar } from '../hooks/useXAvatar';

export const OperatorIdentity = ({ handle }) => {
  const avatar = useXAvatar(handle);
  return <div className="operator">
    <div className="operator-icon" data-testid="operator-avatar" data-avatar-status={avatar.status}>
      {avatar.image ? <img src={avatar.image.src} alt={`Public X profile photo for @${handle}`} referrerPolicy="no-referrer" data-testid="operator-profile-image" /> : avatar.status === 'loading' ? <LoaderCircle className="animate-spin" size={17} /> : <UserRound size={19} />}
    </div>
    <div><span className="operator-label" data-testid="operator-label">01 / OPERATOR</span><p data-testid="operator-handle">@{handle}</p></div>
    <Link to="/" data-testid="switch-handle-link">switch <ArrowRight size={12} /></Link>
  </div>;
};