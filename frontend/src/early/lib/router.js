import { forwardRef } from 'react';
import { Link as RouterLink, Navigate as RouterNavigate, useNavigate as useRouterNavigate } from 'react-router-dom';
export { useParams } from 'react-router-dom';

const earlyPath = to => typeof to === 'string' && to.startsWith('/') && !to.startsWith('/early') ? `/early${to === '/' ? '' : to}` : to;
export const Link = forwardRef(({ to, ...props }, ref) => <RouterLink ref={ref} to={earlyPath(to)} {...props} />);
export const Navigate = ({ to, ...props }) => <RouterNavigate to={earlyPath(to)} {...props} />;
export function useNavigate() {
  const navigate = useRouterNavigate();
  return (to, options) => navigate(earlyPath(to), options);
}