import { Heart, MessageSquare, Repeat2, Send } from 'lucide-react';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';

const Field = ({ name, label, value, onChange, multiline = false, disabled }) => {
  const Component = multiline ? Textarea : Input;
  return <div className="admin-field">
    <label htmlFor={`admin-${name}`}>{label}</label>
    <Component id={`admin-${name}`} type={multiline ? undefined : 'url'} rows={multiline ? 4 : undefined} maxLength={multiline ? 4000 : 2048} required value={value} onChange={event => onChange(name, event.target.value)} disabled={disabled} spellCheck={multiline} autoComplete="off" data-testid={`admin-${name.replaceAll('_', '-')}-input`} />
  </div>;
};

export const CampaignFields = ({ values, onChange, disabled }) => {
  const field = (name, label, multiline = false) => <Field name={name} label={label} value={values[name]} onChange={onChange} disabled={disabled} multiline={multiline} />;
  return <div className="admin-fields">
    <section className="admin-setting-section" aria-labelledby="admin-links-title">
      <div className="admin-section-heading"><span>01</span><h2 id="admin-links-title" data-testid="admin-links-heading">Görev bağlantıları</h2></div>
      <div className="admin-link-grid">
        <div><div className="admin-field-name"><Heart size={17} /> LIKE</div>{field('like_url', 'Like bağlantısı')}</div>
        <div><div className="admin-field-name"><Repeat2 size={17} /> REPOST</div>{field('repost_url', 'Repost bağlantısı')}</div>
      </div>
    </section>
    <section className="admin-setting-section" aria-labelledby="admin-reply-title">
      <div className="admin-section-heading"><span>02</span><h2 id="admin-reply-title" data-testid="admin-reply-heading"><MessageSquare size={17} /> Reply</h2></div>
      {field('reply_text', 'Reply metni', true)}
      {field('reply_url', 'Reply metninin altındaki bağlantı')}
    </section>
    <section className="admin-setting-section" aria-labelledby="admin-claim-title">
      <div className="admin-section-heading"><span>03</span><h2 id="admin-claim-title" data-testid="admin-claim-heading"><Send size={17} /> CLAIM ON X</h2></div>
      {field('claim_text', 'Paylaşım metni', true)}
    </section>
  </div>;
};