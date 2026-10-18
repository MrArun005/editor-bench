// Hidden check for S5 (includes S4's), copied in only while the check runs. Not shown to the agent.
import { expect } from 'chai';
import { stripEndSlash } from '../../utils/shared.utils';

describe('token-bench S5: stripEndSlash', () => {
  it('removes every trailing slash', () => {
    expect(stripEndSlash('/cats///')).to.equal('/cats');
    expect(stripEndSlash('/cats')).to.equal('/cats');
  });
  it('keeps the root for a path of only slashes', () => {
    expect(stripEndSlash('/')).to.equal('/');
    expect(stripEndSlash('///')).to.equal('/');
  });
});
