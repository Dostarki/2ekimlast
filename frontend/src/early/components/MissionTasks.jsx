import { ArrowUpRight, Check, Copy, Heart, MessageSquare, Radio, Repeat2 } from 'lucide-react';
import { Checkbox } from './ui/checkbox';
import { toast } from './ui/sonner';

const icons = { follow: Radio, like: Heart, repost: Repeat2, comment: MessageSquare };
export const MissionTasks = ({ config, draft, update }) => {
  const done = config.tasks.filter(task => draft.tasks[task.id]).length;
  const copyReply = async () => {
    try { await navigator.clipboard.writeText(config.comment_message); toast.success(<span data-testid="reply-copied-message">Reply copied.</span>); }
    catch (_) { toast.error(<span data-testid="reply-copy-error">Select and copy the reply text below.</span>); }
  };
  return <section className="mission-tasks" data-testid="mission-tasks"><div className="console-section-heading"><h2 data-testid="tasks-heading"><span>02</span> TASKS</h2><span className="task-meter" data-testid="task-progress">{config.tasks.map(task => <i key={task.id} className={draft.tasks[task.id] ? 'filled' : ''} />)}<b>{done}/4</b></span></div>
    <div className="task-list">{config.tasks.map((task, index) => { const Icon = icons[task.id]; const completed = !!draft.tasks[task.id]; return <div className={`mission-task ${completed ? 'task-done' : ''}`} key={task.id} data-testid={`task-${task.id}`}><span className="task-number">0{index + 1}</span><Icon className="task-icon" size={18} /><div className="task-info"><span className="task-title" data-testid={`task-${task.id}-title`}>{task.title}</span><p data-testid={`task-${task.id}-text`}>{task.text}</p><label className="task-confirm" htmlFor={`confirm-${task.id}`} data-testid={`task-${task.id}-confirm-label`}><Checkbox id={`confirm-${task.id}`} checked={completed} disabled={!draft.opened[task.id] || !!draft.result} onCheckedChange={checked => update(current => ({ tasks: { ...current.tasks, [task.id]: !!checked } }))} data-testid={`task-${task.id}-checkbox`} />{completed ? 'Marked complete' : 'I completed this task'}</label></div><a href={task.url} target="_blank" rel="noopener noreferrer" className="task-open" onClick={() => update(current => ({ opened: { ...current.opened, [task.id]: true } }))} data-testid={`task-${task.id}-link`}>{task.action}<ArrowUpRight size={13} /></a>{completed && <Check className="task-complete-mark" size={12} aria-hidden="true" />}</div>; })}</div>
    <div className="reply-draft"><p data-testid="comment-draft-text">{config.comment_message}</p><button type="button" onClick={copyReply} data-testid="copy-reply-button"><Copy size={12} /> Copy reply</button></div>
    <p className="self-declaration" data-testid="task-verification-note">USER-DECLARED COMPLETION <span>·</span> NOT VERIFIED BY X</p>
  </section>;
};