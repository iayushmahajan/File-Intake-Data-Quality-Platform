import {render, screen, fireEvent} from '@testing-library/react';
import {afterEach, expect, it, vi} from 'vitest';
import {createRef} from 'react';
import {Dialog} from '../../components/ui/dialog';
import fixture from '../../../scripts/fixtures/investigation.json';
import {type Evidence} from './contracts';
import {CaseDetailWindow} from './CaseDetailWindow';
afterEach(()=>vi.unstubAllGlobals());
it('exposes bounded keyboard resizing, clamps at both ends and adapts to viewport changes',()=>{
  vi.stubGlobal('innerWidth',1440);
  render(<Dialog open><CaseDetailWindow title="Source records" evidence={fixture as unknown as Evidence} wide resizable returnFocus={createRef()}><p>Evidence</p></CaseDetailWindow></Dialog>);
  const handle=screen.getByRole('separator',{name:'Resize source panel'});
  expect(handle).toHaveAttribute('aria-valuemin','680'); expect(handle).toHaveAttribute('aria-valuemax','1280'); expect(handle).toHaveAttribute('aria-valuenow','1060');
  fireEvent.keyDown(handle,{key:'ArrowLeft'});expect(handle).toHaveAttribute('aria-valuenow','1092');
  fireEvent.keyDown(handle,{key:'ArrowRight'});expect(handle).toHaveAttribute('aria-valuenow','1060');
  fireEvent.keyDown(handle,{key:'Home'});fireEvent.keyDown(handle,{key:'ArrowRight'});expect(handle).toHaveAttribute('aria-valuenow','680');
  fireEvent.keyDown(handle,{key:'End'});fireEvent.keyDown(handle,{key:'ArrowLeft'});expect(handle).toHaveAttribute('aria-valuenow','1280');
  vi.stubGlobal('innerWidth',900);fireEvent(window,new Event('resize'));expect(handle).toHaveAttribute('aria-valuemax','868');expect(handle).toHaveAttribute('aria-valuenow','868');
});
