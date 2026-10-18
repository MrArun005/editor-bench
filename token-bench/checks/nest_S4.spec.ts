// Hidden check for S4, copied in only while the check runs. Not shown to the agent.
import { expect } from 'chai';
import { stripEndSlash } from '../../utils/shared.utils';

describe('token-bench S4: stripEndSlash', () => {
  it('removes every trailing slash', () => {
    expect(stripEndSlash('/cats///')).to.equal('/cats');
    expect(stripEndSlash('/cats/')).to.equal('/cats');
    expect(stripEndSlash('/cats')).to.equal('/cats');
  });
});
