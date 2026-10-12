import { lazy, Suspense, useEffect, useState } from 'react';
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { Alert, Button, Form, Input, Select, Spin, Tag } from 'antd';
import { BookOutlined, FileTextOutlined, SearchOutlined, MessageOutlined, LogoutOutlined, ArrowRightOutlined } from '@ant-design/icons';
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, errorText, queryClient, setToken } from './api';
import type { KB, Principal } from './types';
const Documents = lazy(() => import('./Documents'));
const Workspace = lazy(() => import('./Workspace'));

function Login({ onLogin }: { onLogin: (p: Principal, tenant: string) => void }) {
  const login = useMutation({ mutationFn: async (values: { tenant_name: string; username: string; password: string }) => {
    const { data } = await api.post('/auth/login', values);
    setToken(data.access_token);
    try { const me = await api.get<Principal>('/auth/me'); return { me: me.data, tenant: values.tenant_name }; }
    catch (e) { setToken(''); throw e; }
  }, onSuccess: result => onLogin(result.me, result.tenant) });
  return <div className="login-page">
    <section className="login-story"><div className="brand"><BookOutlined /> 知序 <span>SUPPORT KNOWLEDGE</span></div>
      <div><div className="eyebrow">企业软件交付与技术支持</div><h1>让每一次解答，<br />都有据可循。</h1><p>连接交付手册、故障案例与技术知识。<br />从文档到证据，让支持工作更清晰。</p>
      <div className="story-flow"><span>文档解析</span><i>→</i><span>混合检索</span><i>→</i><span>引用回答</span></div></div>
      <small>知识库权限隔离 · Dense + Sparse · 可追溯引用</small></section>
    <section className="login-form"><div className="eyebrow">WORKSPACE ACCESS</div><h2>登录知识工作台</h2><p className="muted">使用所属租户的账号访问授权资料。</p>
      {login.isError && <Alert type="error" showIcon message={errorText(login.error)} />}
      <Form layout="vertical" onFinish={v => login.mutate(v)} initialValues={{ tenant_name: 'customer-a', username: 'admin' }}>
        <Form.Item name="tenant_name" label="租户" rules={[{ required: true }]}><Input size="large" autoComplete="organization" /></Form.Item>
        <Form.Item name="username" label="用户名" rules={[{ required: true }]}><Input size="large" autoComplete="username" /></Form.Item>
        <Form.Item name="password" label="密码" rules={[{ required: true }]}><Input.Password size="large" autoComplete="current-password" /></Form.Item>
        <Button block size="large" type="primary" htmlType="submit" loading={login.isPending}>进入工作台 <ArrowRightOutlined /></Button>
      </Form><p className="login-note">令牌仅保存在当前页面内存中，刷新后需要重新登录。</p>
    </section>
  </div>;
}

export default function App() {
  const [principal, setPrincipal] = useState<Principal | null>(null);
  const [tenant, setTenant] = useState('');
  const [kb, setKB] = useState('');
  const [expired, setExpired] = useState(false);
  const location = useLocation();
  const logout = () => { setToken(''); setPrincipal(null); setKB(''); queryClient.clear(); };
  useEffect(() => {
    const handler = () => { logout(); setExpired(true); };
    window.addEventListener('session-expired', handler);
    return () => window.removeEventListener('session-expired', handler);
  }, []);
  const bases = useQuery({ queryKey: ['bases', principal?.user_id], enabled: !!principal,
    queryFn: async () => (await api.get<KB[]>('/knowledge-bases')).data });
  const activeKB = bases.data?.some(b => b.id === kb) ? kb : bases.data?.[0]?.id || '';
  if (!principal) return <>{expired && <Alert banner type="warning" message="登录已失效，请重新登录。" />}<Login onLogin={(p, t) => { queryClient.clear(); setPrincipal(p); setTenant(t); setExpired(false); }} /></>;
  const nav = [{ to: '/documents', label: '文档中心', icon: <FileTextOutlined /> },
    { to: '/search', label: '检索实验室', icon: <SearchOutlined /> },
    { to: '/chat', label: '知识问答', icon: <MessageOutlined /> }];
  return <div className="shell"><aside className="sidebar">
    <Link to="/documents" className="brand"><BookOutlined /> 知序</Link><div className="sidebar-caption">技术支持知识工作台</div>
    <div className="nav-label">工作空间</div><nav>{nav.map(item => <Link key={item.to} to={item.to} className={location.pathname === item.to ? 'active' : ''}>{item.icon}{item.label}</Link>)}</nav>
    <div className="sidebar-bottom"><Tag color="cyan">第一阶段 · 开发版</Tag><p>答案来自授权资料。<br />重要操作请核对原始证据。</p></div>
  </aside><div className="main-area"><header className="topbar"><span className="workspace-label">企业知识库 <span>/</span> {tenant}</span>
    <div className="topbar-actions"><Select aria-label="当前知识库" placeholder="选择知识库" loading={bases.isLoading} value={activeKB || undefined} onChange={setKB} options={bases.data?.map(b => ({ label: b.name, value: b.id }))} style={{ minWidth: 180 }} />
    <Tag>{principal.role === 'admin' ? '管理员' : '成员'}</Tag><Button icon={<LogoutOutlined />} onClick={logout}>退出</Button></div></header>
    <main key={`${principal.user_id}:${activeKB}`}>
      {bases.isError ? <Alert type="error" showIcon message={errorText(bases.error)} action={<Button onClick={() => bases.refetch()}>重试</Button>} /> : bases.isLoading ? <Spin /> : !activeKB ? <Alert type="info" message="当前账号暂无可访问的知识库，请联系管理员。" /> :
        <Suspense fallback={<Spin />}><Routes><Route path="/documents" element={<Documents kb={activeKB} admin={principal.role === 'admin'} />} />
          <Route path="/search" element={<Workspace key="search" kb={activeKB} mode="search" />} />
          <Route path="/chat" element={<Workspace key="chat" kb={activeKB} mode="chat" />} />
          <Route path="*" element={<Navigate to="/documents" replace />} /></Routes></Suspense>}
    </main><footer>知序 · Enterprise Support RAG <span>基于证据，而非猜测</span></footer></div></div>;
}
