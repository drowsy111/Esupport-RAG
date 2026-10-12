import { describe, expect, it } from 'vitest';
import { AxiosError } from 'axios';
import { renderToStaticMarkup } from 'react-dom/server';
import { createElement } from 'react';
import { errorText, isPending } from './api';
import { SafeMarkdown } from './Workspace';

describe('client contracts', () => {
  it('only polls nonterminal task states', () => {
    expect(isPending('QUEUED')).toBe(true);
    expect(isPending('RUNNING')).toBe(true);
    expect(isPending('READY')).toBe(false);
    expect(isPending('FAILED')).toBe(false);
  });
  it('explains network failures without exposing request credentials', () => {
    expect(errorText(new AxiosError('secret request details'))).toContain('无法连接 API');
    expect(errorText(new AxiosError('secret request details'))).not.toContain('secret');
  });
  it('does not render raw HTML or remote images', () => {
    const html = renderToStaticMarkup(createElement(SafeMarkdown, {
      children: '<script>alert(1)</script>\n\n![tracking](https://example.com/pixel)\n\n[unsafe](javascript:alert(1))',
    }));
    expect(html).not.toContain('<script');
    expect(html).not.toContain('<img');
    expect(html).not.toContain('javascript:');
  });
});
