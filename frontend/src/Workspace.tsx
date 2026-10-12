import { useState } from 'react';
import { Alert, Button, Collapse, Empty, Form, Input, Space, Tag } from 'antd';
import { ArrowRightOutlined, SearchOutlined, MessageOutlined } from '@ant-design/icons';
import { useMutation } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api, errorText } from './api';
import type { Answer, QueryInput, SearchResult, Trace, WindowEvidence } from './types';

export function TracePanel({ trace }: { trace: Trace }) {
  return <Collapse ghost size="small" items={[{ key: 'trace', label: '查看检索与请求信息', children: <dl className="trace">{Object.entries(trace).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl> }]} />;
}
export function SafeMarkdown({ children }: { children: string }) {
  return <div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={{
    img: () => <span className="muted">[外部图片未加载]</span>,
    a: ({ href, children: label }) => <a href={href} target="_blank" rel="noopener noreferrer">{label}</a>,
  }}>{children}</ReactMarkdown></div>;
}

function WindowQuote({ quote, matched_text, sources }: WindowEvidence & { quote: string }) {
  return <>
    {matched_text && matched_text !== quote && <><small className="muted">命中原句 · 标注位置对应此句</small><p className="source-text">{matched_text}</p><small className="muted">完整上下文</small></>}
    <blockquote className="source-text">{quote}</blockquote>
    {sources && sources.length > 1 && <details><summary>查看各片段来源位置</summary>{sources.map(s => <div key={s.chunk_id}><small className="muted">{s.page != null ? `第 ${s.page} 页` : s.anchor}</small><p className="source-text">{s.text}</p></div>)}</details>}
  </>;
}

export default function Workspace({ kb, mode }: { kb: string; mode: 'search' | 'chat' }) {
  const [form] = Form.useForm();
  const [history, setHistory] = useState<{ query: string; answer: Answer }[]>([]);
  const [searchedQuery, setSearchedQuery] = useState('');
  const [result, setResult] = useState<SearchResult | null>(null);
  const searchMode = mode === 'search';
  const action = useMutation({ mutationFn: async (values: { query: string; product_id?: string; product_version?: string; deployment_mode?: string }) => {
    const { query, ...context } = values;
    const body: QueryInput = { query: query.trim(), knowledge_base_id: kb,
      context: Object.fromEntries(Object.entries(context).filter(([, v]) => v?.trim()).map(([k, v]) => [k, v!.trim()])) };
    if (searchMode) { const response = await api.post<SearchResult>('/search', body); return { query: body.query, search: response.data }; }
    const response = await api.post<Answer>('/chat/completions', body);
    return { query: body.query, answer: response.data };
  }, onSuccess: data => {
    if (data.search) { setResult(data.search); setSearchedQuery(data.query); }
    if (data.answer) setHistory(old => [...old, { query: data.query, answer: data.answer! }]);
  } });
  return <><section className="page-heading"><div><div className="eyebrow">{searchMode ? 'RETRIEVAL LAB' : 'EVIDENCE-BASED ANSWERS'}</div><h1>{searchMode ? '检索实验室' : '知识问答'}</h1><p>{searchMode ? '观察哪些证据被选中，让每一次检索都可解释。' : '从授权知识中寻找答案，并回到原文验证。'}</p></div>
    <Tag color="cyan">{searchMode ? 'Dense + Sparse → RRF → Reranker' : '带引用 · 单轮检索'}</Tag></section>
    <div className="workspace-grid"><section className="surface query-panel"><h2>{searchMode ? '检索条件' : '提出问题'}</h2>
      <Form form={form} layout="vertical" disabled={action.isPending} onFinish={v => action.mutate(v)}>
        <Form.Item name="query" label={searchMode ? '查询内容' : '你的问题'} rules={[{ required: true, whitespace: true, message: '请输入问题或检索内容' }]}><Input.TextArea rows={5} maxLength={2000} showCount placeholder="例如：部署时出现 DEMO-DB-001，应该先检查什么？" /></Form.Item>
        <div className="query-divider">适用范围 · 可选</div>
        <Form.Item name="product_id" label="产品标识"><Input maxLength={100} placeholder="例如 supporthub-demo" /></Form.Item>
        <Form.Item name="product_version" label="产品版本"><Input maxLength={50} placeholder="例如 2.4.1" /></Form.Item>
        <Form.Item name="deployment_mode" label="部署方式"><Input maxLength={50} placeholder="例如 docker_compose" /></Form.Item>
        <Button type="primary" block size="large" htmlType="submit" loading={action.isPending} icon={searchMode ? <SearchOutlined /> : <ArrowRightOutlined />}>{searchMode ? '检索证据' : '获取有据可循的回答'}</Button>
      </Form><p className="muted">只检索当前知识库中有权访问、已发布且适用的资料。</p>
      {!searchMode && <Alert type="info" message="当前每次提问独立检索。页面记录不会作为模型上下文；追问请补充完整条件。" />}
    </section><section className="results-panel" aria-live="polite" aria-busy={action.isPending}>
      {action.isError && <Alert type="error" showIcon message={errorText(action.error)} />}
      {action.isPending && <Alert type="info" showIcon message={searchMode ? '正在编码查询、混合检索和精排…' : '正在检索证据并生成回答，请稍候…'} />}
      {searchMode ? result ? <><div className="section-bar"><h2>检索结果 <span className="count-badge">{result.candidates.length}</span></h2><Tag>最近完成的查询</Tag></div><p className="query-summary">{searchedQuery}</p>
        {!result.candidates.length && <div className="surface"><Empty description="没有找到适用证据。检查文档是否 READY，或调整问题与过滤条件。" /></div>}
        {result.candidates.map((c, i) => <article className="surface evidence-card" key={c.chunk_id}><div className="evidence-top"><span className="rank">{String(i + 1).padStart(2, '0')}</span><div><h3>{c.document_name}</h3><small className="muted">修订 v{c.revision} · {c.page != null ? `第 ${c.page} 页` : c.anchor || '正文'} · {c.source_kind}</small></div></div>
          <div className="score-row"><Tag>RRF {c.fusion_score.toFixed(4)}</Tag><Tag color="cyan">精排 {c.rerank_score?.toFixed(4) ?? '—'}</Tag>{c.product_version && <Tag>产品 {c.product_version}</Tag>}</div>
          {c.title_path && <p className="muted">{c.title_path}</p>}
          {c.matched_text && c.matched_text !== c.text && <><small className="muted">命中原句 · 定位对应此句</small><p className="source-text">{c.matched_text}</p><small className="muted">扩展上下文 · {c.sources?.length ?? 1} 个片段</small></>}
          <p className="source-text">{c.text}</p><details><summary>片段标识与来源位置</summary><code>{c.chunk_id}</code>{c.sources?.map(s => <div key={s.chunk_id}><small>{s.page != null ? `第 ${s.page} 页` : s.anchor}</small> <code>{s.chunk_id}</code></div>)}</details>
        </article>)}<TracePanel trace={result.trace} /><p className="muted">此处显示精排后返回的候选，不是 Dense/Sparse 两路原始召回。分数不是置信概率。</p></> : <Welcome search /> :
        history.length ? <><div className="section-bar"><h2>本页问答记录</h2><Button disabled={action.isPending} onClick={() => setHistory([])}>清空页面记录</Button></div><p className="muted">清空仅影响当前页面，不删除服务器保存的会话。</p>{history.map((item, index) => <article className="answer-turn" key={item.answer.request_id}>
          <div className="question"><span>Q{index + 1}</span>{item.query}</div><div className="surface answer-card"><div className="section-bar"><h3>知序回答</h3><Tag color={item.answer.status === 'answered' ? 'success' : 'warning'}>{item.answer.status === 'answered' ? '基于资料回答' : item.answer.status === 'needs_clarification' ? '需要补充条件' : '证据不足'}</Tag></div>
            <SafeMarkdown>{item.answer.answer}</SafeMarkdown>
            {item.answer.citations.length > 0 && <><div className="query-divider">引用证据 · {item.answer.citations.length}</div><Collapse items={item.answer.citations.map(c => ({ key: c.citation_id, label: <Space wrap><Tag>{c.citation_id}</Tag><span>{c.document_name}</span><small>v{c.revision} · {c.page != null ? `第 ${c.page} 页` : c.anchor}</small></Space>, children: <><WindowQuote {...c} /><small className="muted">来源：{c.source_kind} · 文档 {c.document_id}</small></> }))} /></>}
            <TracePanel trace={item.answer.trace} /></div></article>)}</> : <Welcome />}
    </section></div>
  </>;
}

function Welcome({ search = false }: { search?: boolean }) {
  return <div className="surface welcome"><div className="welcome-icon">{search ? <SearchOutlined /> : <MessageOutlined />}</div><h2>{search ? '从一个问题，找到相关证据' : '让知识成为可验证的答案'}</h2><p>{search ? '输入错误码、故障现象或配置问题。检索结果将展示来源、原文与精排分数。' : '先上传并完成文档处理，再提出具体问题。每个回答都应有可以核对的来源。'}</p><div className="welcome-features"><span>01　授权资料</span><span>02　混合检索</span><span>03　原文证据</span></div></div>;
}
