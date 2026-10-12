import { useRef, useState } from 'react';
import { Alert, App, Button, Descriptions, Drawer, Empty, Form, Input, Modal, Select, Space, Switch, Table, Tag, Upload } from 'antd';
import { CloudUploadOutlined, FileTextOutlined, ReloadOutlined } from '@ant-design/icons';
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, errorText, isPending, queryClient } from './api';
import type { Doc, Job, UploadResult } from './types';

const labels: Record<string, string> = { READY: '已就绪', FAILED: '处理失败', QUEUED: '排队中', RUNNING: '处理中', UNKNOWN: '未知' };
export function Status({ value }: { value: string }) { return <Tag color={value === 'READY' ? 'success' : value === 'FAILED' ? 'error' : 'processing'}>{labels[value] || value}</Tag>; }
function JobPanel({ id, admin, onChange }: { id: string; admin: boolean; onChange: () => void }) {
  const job = useQuery({ queryKey: ['job', id], queryFn: async () => (await api.get<Job>(`/jobs/${id}`)).data,
    refetchInterval: q => q.state.data && isPending(q.state.data.status) ? 2000 : false });
  const retry = useMutation({ mutationFn: () => api.post(`/jobs/${id}/retry`), onSuccess: () => { job.refetch(); onChange(); } });
  return <Space direction="vertical" style={{ width: '100%' }}>
    {job.isError && <Alert type="error" message={errorText(job.error)} />}
    {job.data && <Descriptions column={1} bordered size="small" items={[
      { key: 'id', label: '任务 ID', children: <code>{id}</code> },
      { key: 'status', label: '状态', children: <Status value={job.data.status} /> },
      { key: 'stage', label: '处理阶段', children: job.data.stage },
      { key: 'attempts', label: '执行次数', children: job.data.attempts },
      { key: 'error', label: '错误码', children: job.data.error_code || '—' },
    ]} />}
    {retry.isError && <Alert type="error" message={errorText(retry.error)} />}
    <Space><Button onClick={() => job.refetch()} loading={job.isFetching}>刷新状态</Button>
      {admin && job.data?.status === 'FAILED' && <Button type="primary" onClick={() => retry.mutate()} loading={retry.isPending}>重试原任务</Button>}</Space>
    <p className="muted">完成或失败后停止自动轮询。失败请先排除原因，再重试原任务。</p>
  </Space>;
}

export default function Documents({ kb, admin }: { kb: string; admin: boolean }) {
  const { message } = App.useApp();
  const [page, setPage] = useState(1);
  const [modal, setModal] = useState(false);
  const [target, setTarget] = useState<Doc | null>(null);
  const [jobID, setJobID] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [form] = Form.useForm();
  const idempotency = useRef<string | null>(null);
  const docs = useQuery({ queryKey: ['documents', kb, page],
    queryFn: async () => (await api.get<{ items: Doc[]; total: number }>('/documents', { params: { knowledge_base_id: kb, page, page_size: 10 } })).data,
    refetchInterval: q => q.state.data?.items.some(d => isPending(d.status)) ? 3000 : false });
  const refresh = () => { queryClient.invalidateQueries({ queryKey: ['documents', kb] }); };
  const send = useMutation({ mutationFn: async (values: Record<string, string | boolean>) => {
    if (!file) throw new Error('请选择文件');
    const body = new FormData(); body.append('file', file); body.append('knowledge_base_id', kb);
    Object.entries(values).forEach(([key, value]) => { if (value !== undefined && value !== null) body.append(key, String(value)); });
    if (target) body.append('document_id', target.id);
    idempotency.current ||= crypto.randomUUID();
    return (await api.post<UploadResult>('/documents/upload', body, { headers: { 'Idempotency-Key': idempotency.current } })).data;
  }, onSuccess: data => { setModal(false); setJobID(data.job_id); setPage(1); refresh();
    message.success(data.replayed ? '已返回原请求的任务' : data.reused ? '资料已存在，未重复入库' : '上传已受理'); } });
  function openUpload(document: Doc | null) {
    setTarget(document); setFile(null); form.resetFields(); send.reset(); idempotency.current = null;
    form.setFieldsValue({ product_id: document?.product_id || '', product_version: document?.product_version || '',
      deployment_mode: document?.deployment_mode || '', source_kind: document?.source_kind || 'uploaded', source_url: document?.source_url || '', allow_same_name: false });
    setModal(true);
  }
  return <><section className="page-heading"><div><div className="eyebrow">DOCUMENT LIBRARY</div><h1>文档中心</h1><p>管理知识来源，追踪每一份资料从上传到可检索的过程。</p></div>
    {admin && <Button type="primary" size="large" icon={<CloudUploadOutlined />} onClick={() => openUpload(null)}>上传文档</Button>}</section>
    <div className="stats-row"><div><span>当前知识库文档</span><strong>{docs.data?.total ?? '—'}</strong></div><div><span>支持格式</span><strong className="stat-text">MD / PDF / DOCX</strong></div><div><span>上传策略</span><strong className="stat-text">内容去重 · 版本保留</strong></div></div>
    <section className="surface"><div className="section-bar"><h2>知识来源</h2><Button icon={<ReloadOutlined />} onClick={refresh} loading={docs.isFetching}>刷新</Button></div>
      {docs.isError && <Alert type="error" showIcon message={errorText(docs.error)} />}
      <Table<Doc> rowKey="id" dataSource={docs.data?.items} loading={docs.isLoading} scroll={{ x: 850 }} locale={{ emptyText: <Empty description="还没有文档，上传第一份技术资料开始构建知识库。" /> }}
        pagination={{ current: page, pageSize: 10, total: docs.data?.total, showSizeChanger: false, onChange: setPage }} columns={[
          { title: '文档', dataIndex: 'name', render: (name, row) => <div className="doc-name"><FileTextOutlined /><div><strong>{name}</strong><small>{row.product_id || '通用资料'} · {row.product_version || '未限定产品版本'}</small></div></div> },
          { title: '修订', render: (_, row) => <><Tag>v{row.revision ?? '?'}</Tag>{row.published_version_id && row.published_version_id !== row.version_id && <small>旧版仍可用</small>}</> },
          { title: '处理状态', render: (_, row) => <><Status value={row.status} /><small className="block muted">{row.error_code || row.stage}</small></> },
          { title: '操作', render: (_, row) => <Space><Button size="small" disabled={!row.job_id} onClick={() => setJobID(row.job_id)}>任务详情</Button>{admin && <Button size="small" onClick={() => openUpload(row)}>更新版本</Button>}</Space> },
        ]} />
    </section>
    <Modal title={target ? `更新版本 · ${target.name}` : '上传知识文档'} open={modal} onCancel={() => { if (!send.isPending) setModal(false); }} footer={null} maskClosable={!send.isPending} closable={!send.isPending} width={620}>
      <Alert type="info" showIcon message={target ? '新版处理成功后才替换发布版本；失败时旧版继续可检索。' : '相同内容和业务信息会返回已有资料，不重复创建任务。'} />
      <Form form={form} layout="vertical" disabled={send.isPending} onValuesChange={() => { idempotency.current = null; send.reset(); }} onFinish={v => send.mutate(v)}>
        <Form.Item label="文件（不超过 10 MiB）" required><Upload.Dragger accept=".md,.pdf,.docx" maxCount={1} disabled={send.isPending} fileList={file ? [{ uid: 'selected', name: file.name, status: 'done' }] : []}
          beforeUpload={f => { if (f.size > 10 * 1024 * 1024 || !/\.(md|pdf|docx)$/i.test(f.name)) { message.error('请选择不超过 10 MiB 的 MD、PDF 或 DOCX 文件'); return Upload.LIST_IGNORE; } setFile(f); idempotency.current = null; send.reset(); return false; }}
          onRemove={() => { setFile(null); idempotency.current = null; }}><CloudUploadOutlined className="upload-icon" /><p>点击或拖拽文件到这里</p><small>PDF 目前仅支持可提取文本的页面</small></Upload.Dragger></Form.Item>
        <div className="form-grid"><Form.Item name="product_id" label="产品标识"><Input maxLength={100} /></Form.Item><Form.Item name="product_version" label="产品版本"><Input maxLength={50} /></Form.Item>
          <Form.Item name="deployment_mode" label="部署方式"><Input maxLength={50} placeholder="例如 docker_compose" /></Form.Item><Form.Item name="source_kind" label="资料来源"><Select options={[{ value: 'uploaded', label: '上传资料' }, { value: 'official', label: '官方资料' }, { value: 'synthetic', label: '模拟资料' }]} /></Form.Item></div>
        <Form.Item name="source_url" label="来源地址（可选）"><Input maxLength={1000} /></Form.Item>
        {!target && <Form.Item name="allow_same_name" label="允许同名不同内容另存" valuePropName="checked"><Switch /></Form.Item>}
        {send.isError && <Alert type="error" showIcon message={errorText(send.error)} />}
        <Button type="primary" block htmlType="submit" loading={send.isPending} disabled={!file}>提交{target ? '新版本' : '文档'}</Button>
      </Form>
    </Modal>
    <Drawer title="入库任务" open={!!jobID} onClose={() => { setJobID(null); refresh(); }} width={520}>{jobID && <JobPanel key={jobID} id={jobID} admin={admin} onChange={refresh} />}</Drawer>
  </>;
}
