import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from database import Database
from main import CLI, main
from seed import preparar
from services import Sistema


class SistemaTest(unittest.TestCase):
    def setUp(self):
        self.db = Database(':memory:')
        self.s = Sistema(self.db)
        self.o = self.s.cadastrar('Organizador', 'org@local', 'segredo', organizador=True)
        self.a = self.s.cadastrar('Ana', 'ana@local', 'segredo')
        self.b = self.s.cadastrar('Bruno', 'bruno@local', 'segredo')
        self.m = self.s.cadastrar('Mentor', 'mentor@local', 'segredo')
        self.j = self.s.cadastrar('Jurado', 'jurado@local', 'segredo')
        self.h = self.s.organizador(self.o).salvar_hackathon('Evento', '2026-09-01', '2026-09-30', 2)
        for u, papel in ((self.a, 'participante'), (self.b, 'participante'), (self.m, 'mentor'), (self.j, 'jurado')):
            self.s.hackathon(self.h).entrar(u, papel)
        self.e = self.s.participante(self.a, self.h).criar_equipe('Equipe A')

    def tearDown(self):
        self.db.close()

    def projeto(self):
        self.s.equipe(self.e).salvar_projeto(self.a, 'Solução', 'Descrição', 'Educação')
        return self.s.equipe(self.e).visualizar_projeto().id

    def test_autenticacao(self):
        self.assertEqual(self.s.login(' ANA@LOCAL ', 'segredo'), self.a)
        with self.assertRaises(ValueError):
            self.s.login('ana@local', 'errada')
        with self.assertRaises(ValueError):
            self.s.cadastrar('Duplicado', 'ANA@LOCAL', 'segredo')
        self.assertNotIn('segredo', self.s.obter('usuarios', self.a)['senha'])

    def test_papeis_por_hackathon(self):
        outro = self.s.organizador(self.o).salvar_hackathon('Outro', '2026-10-01', '2026-10-02', 1)
        self.s.hackathon(outro).entrar(self.a, 'jurado')
        self.assertEqual(self.s.papel(self.a, outro), 'jurado')
        with self.assertRaises(ValueError):
            self.s.hackathon(self.h).entrar(self.a, 'mentor')
        self.s.atuacao(self.b, self.h).sair_hackathon()
        self.s.hackathon(self.h).entrar(self.b, 'mentor')
        self.assertEqual(self.s.papel(self.b, self.h), 'mentor')

    def test_lideranca_e_saida(self):
        with self.assertRaises(ValueError):
            self.s.atuacao(self.a, self.h).sair_hackathon()
        self.s.participante(self.b, self.h).entrar_equipe(self.e)
        with self.assertRaises(ValueError):
            self.s.atuacao(self.a, self.h).sair_hackathon()
        with self.assertRaises(ValueError):
            self.s.equipe(self.e).remover_participante(self.a, self.a)
        self.s.equipe(self.e).transferir_lideranca(self.a, self.b)
        self.s.atuacao(self.a, self.h).sair_hackathon()
        self.assertFalse(any(p['id'] == self.a for p in self.s.equipe(self.e).visualizar_participantes()))
        self.assertEqual(self.s.obter('equipes', self.e)['lider_id'], self.b)
        self.s.equipe(self.e).excluir(self.b)
        self.s.atuacao(self.b, self.h).sair_hackathon()

    def test_saida_membro_e_remocao(self):
        self.s.participante(self.b, self.h).entrar_equipe(self.e)
        self.s.equipe(self.e).remover_participante(self.a, self.b)
        self.assertEqual(self.s.papel(self.b, self.h), 'participante')
        self.s.participante(self.b, self.h).entrar_equipe(self.e)
        self.s.atuacao(self.b, self.h).sair_hackathon()
        self.assertEqual(len(self.s.equipe(self.e).visualizar_participantes()), 1)

    def test_limite_e_unicidade(self):
        with self.assertRaises(ValueError):
            self.s.participante(self.a, self.h).criar_equipe('Outra')
        with self.assertRaises(ValueError):
            self.s.participante(self.b, self.h).criar_equipe('equipe a')
        self.assertIsNone(self.s.participante(self.b, self.h).visualizar_equipe())
        self.s.participante(self.b, self.h).criar_equipe('Equipe B')
        with self.assertRaises(ValueError):
            self.s.participante(self.b, self.h).entrar_equipe(self.e)
        with self.assertRaises(ValueError):
            self.s.organizador(self.o).salvar_hackathon('Evento', '2026-09-01', '2026-09-30', 1, self.h)
        c = self.s.cadastrar('Carla', 'c@local', 'segredo')
        self.s.hackathon(self.h).entrar(c, 'participante')
        with self.assertRaises(ValueError):
            self.s.participante(c, self.h).criar_equipe('Equipe C')

    def test_permissoes(self):
        p = self.projeto()
        for operacao in (
            lambda: self.s.organizador(self.a).salvar_hackathon('X', '2026-09-01', '2026-09-02', 1),
            lambda: self.s.organizador(self.a).remover_hackathon(self.h),
            lambda: self.s.equipe(self.e).salvar_projeto(self.b, 'X', 'X', 'X'),
            lambda: self.s.equipe(self.e).excluir_projeto(self.b),
            lambda: self.s.equipe(self.e).excluir(self.b),
            lambda: self.s.equipe(self.e).renomear(self.b, 'X'),
            lambda: self.s.mentor(self.j, self.h).salvar_mentoria(self.e, 'X'),
            lambda: self.s.jurado(self.m, self.h).salvar_avaliacao(p, 8, 'X'),
        ):
            with self.subTest(operacao=operacao), self.assertRaises(ValueError):
                operacao()

    def test_historico_e_filtros_individuais(self):
        p = self.projeto()
        self.s.mentor(self.m, self.h).salvar_mentoria(self.e, 'Primeiro comentário')
        self.s.jurado(self.j, self.h).salvar_avaliacao(p, 8, 'Boa solução')
        self.s.atuacao(self.b, self.h).sair_hackathon()
        self.s.hackathon(self.h).entrar(self.b, 'jurado')
        self.assertEqual(len(self.s.jurado(self.j, self.h).visualizar_projetos('avaliados')), 1)
        self.assertEqual(len(self.s.jurado(self.b, self.h).visualizar_projetos('pendentes')), 1)
        self.s.jurado(self.b, self.h).salvar_avaliacao(p, 0, 'Outra avaliação')
        self.assertEqual(len(self.s.jurado(self.b, self.h).visualizar_projetos('avaliados')), 1)
        self.s.atuacao(self.j, self.h).sair_hackathon()
        self.s.atuacao(self.m, self.h).sair_hackathon()
        self.assertEqual(self.db.execute('SELECT count(*) FROM avaliacoes').fetchone()[0], 2)
        self.assertEqual(self.db.execute('SELECT count(*) FROM mentorias').fetchone()[0], 1)
        with self.assertRaises(ValueError):
            self.s.jurado(self.j, self.h).salvar_avaliacao(p, 9, 'Sem vínculo')
        self.s.hackathon(self.h).entrar(self.j, 'jurado')
        self.s.hackathon(self.h).entrar(self.m, 'mentor')
        self.s.jurado(self.j, self.h).salvar_avaliacao(p, 9, 'Revisada')
        self.s.mentor(self.m, self.h).salvar_mentoria(self.e, 'Revisado')
        self.assertEqual(self.s.mentor(self.m, self.h).visualizar_mentorias()[0].comentarios, 'Revisado')
        self.assertEqual(self.s.jurado(self.j, self.h).visualizar_projetos()[0]['nota'], 9)
        self.s.equipe(self.e).salvar_projeto(self.a, 'Novo título', 'Nova descrição', 'Saúde')
        self.assertEqual(self.s.equipe(self.e).visualizar_projeto().id, p)
        self.assertEqual(self.db.execute('SELECT count(*) FROM avaliacoes').fetchone()[0], 2)

    def test_isolamento_eventos_e_validacoes(self):
        p = self.projeto()
        outro = self.s.organizador(self.o).salvar_hackathon('Outro', '2026-10-01', '2026-10-02', 1)
        for u, papel in ((self.b, 'participante'), (self.m, 'mentor'), (self.j, 'jurado')):
            self.s.hackathon(outro).entrar(u, papel)
        for operacao in (
            lambda: self.s.participante(self.b, outro).entrar_equipe(self.e),
            lambda: self.s.mentor(self.m, outro).salvar_mentoria(self.e, 'X'),
            lambda: self.s.jurado(self.j, outro).salvar_avaliacao(p, 9, 'X'),
            lambda: self.s.jurado(self.j, self.h).salvar_avaliacao(p, 1.5, 'X'),
            lambda: self.s.organizador(self.o).salvar_hackathon('X', '2026-02-30', '2026-03-01', 1),
            lambda: self.s.organizador(self.o).salvar_hackathon('X', '2026-09-30', '2026-09-01', 1),
        ):
            with self.subTest(operacao=operacao), self.assertRaises(ValueError):
                operacao()

    def test_exclusoes_sem_orfaos(self):
        p = self.projeto()
        self.s.jurado(self.j, self.h).salvar_avaliacao(p, 8, 'Boa')
        self.s.mentor(self.m, self.h).salvar_mentoria(self.e, 'Dica')
        self.s.organizador(self.o).remover_hackathon(self.h)
        for tabela in ('hackathons', 'inscricoes', 'equipes', 'membros', 'projetos', 'avaliacoes', 'mentorias'):
            self.assertEqual(self.db.execute(f'SELECT count(*) FROM {tabela}').fetchone()[0], 0)
        self.assertEqual(list(self.db.execute('PRAGMA foreign_key_check')), [])

    def test_menu_terminal_fluxo_participante(self):
        # Login, abrir inscrição, consultar equipe, criar projeto e encerrar.
        entradas = ['2', 'ana@local', '3', str(self.h), '3', '4', 'Projeto pelo menu',
                    'Descrição pelo menu', 'Educação', '0', '0', '0', '3']
        saida = io.StringIO()
        with patch('builtins.input', side_effect=entradas), patch('main.getpass', return_value='segredo'), contextlib.redirect_stdout(saida):
            CLI(self.s).executar()
        self.assertEqual(self.s.equipe(self.e).visualizar_projeto().titulo, 'Projeto pelo menu')
        self.assertNotIn('Erro:', saida.getvalue())


    def test_menu_entrada_sem_eventos(self):
        self.s.organizador(self.o).remover_hackathon(self.h)
        with patch('builtins.input', side_effect=['2', '3', '0']) as entrada, contextlib.redirect_stdout(io.StringIO()) as saida:
            CLI(self.s).sessao(self.a)
        self.assertNotIn('ESCOLHA SEU PAPEL', saida.getvalue())
        self.assertTrue(all('ID do hackathon' not in c.args[0] for c in entrada.call_args_list))

    def test_menu_id_invalido_e_cancelamento(self):
        with patch('builtins.input', side_effect=['2', '9999', '2', '0', '0']), contextlib.redirect_stdout(io.StringIO()) as saida:
            CLI(self.s).sessao(self.a)
        self.assertIn('ID não encontrado', saida.getvalue())
        self.assertNotIn('ESCOLHA SEU PAPEL', saida.getvalue())

    def test_seed_banco_existente_preserva_dados(self):
        original = dict(self.s.obter('usuarios', self.a))
        with contextlib.redirect_stdout(io.StringIO()):
            preparar(self.db)
            preparar(self.db)
        self.assertEqual(dict(self.s.obter('usuarios', self.a)), original)
        self.assertEqual(self.s.login('org@local', 'Adm123!'), self.o)
        with self.assertRaises(ValueError):
            self.s.login('org@local', 'segredo')
        self.assertEqual(len(self.s.hackathons()), 2)
        self.assertEqual(self.s.obter('equipes', self.e)['nome'], 'Equipe A')
        pedro = self.s.login('pedro@demo.local', 'Demo123!')
        demo = next(h for h in self.s.hackathons() if h.id != self.h)
        self.assertEqual(len(self.s.jurado(pedro, demo.id).visualizar_projetos('pendentes')), 1)
        self.assertEqual(list(self.db.execute('PRAGMA foreign_key_check')), [])
        self.s.organizador(self.o).remover_hackathon(demo.id)
        with contextlib.redirect_stdout(io.StringIO()):
            preparar(self.db)
        self.assertEqual(len(self.s.hackathons()), 1)


    def test_objetos_de_papel_invalidos_apos_saida(self):
        p = self.projeto()
        participante = self.s.participante(self.b, self.h)
        mentor = self.s.mentor(self.m, self.h)
        jurado = self.s.jurado(self.j, self.h)
        for ator in (participante, mentor, jurado):
            ator.sair_hackathon()
        self.s.hackathon(self.h).entrar(self.b, 'mentor')
        for acao in (
            lambda: participante.entrar_equipe(self.e),
            lambda: participante.criar_equipe('Indevida'),
            lambda: participante.sair_hackathon(),
            lambda: mentor.iniciar_mentoria(self.e, 'Indevida'),
            lambda: jurado.avaliar_projeto(p, 9, 'Indevida'),
        ):
            with self.assertRaises(ValueError):
                acao()
        self.assertEqual(self.s.papel(self.b, self.h), 'mentor')

    def test_entidade_equipe_revalida_lideranca(self):
        equipe = self.s.equipe(self.e)
        self.s.participante(self.b, self.h).entrar_equipe(self.e)
        equipe.transferir_lideranca(self.a, self.b)
        self.assertEqual(equipe.lider_id, self.b)
        with self.assertRaises(ValueError):
            equipe.salvar_projeto(self.a, 'X', 'X', 'X')
        equipe.renomear(self.b, 'Novo nome')
        self.assertEqual(equipe.nome, 'Novo nome')

    def test_metodos_mentoria_avaliacao(self):
        p = self.projeto()
        mentor = self.s.mentor(self.m, self.h)
        mentor.iniciar_mentoria(self.e, 'Inicial')
        with self.assertRaises(ValueError):
            mentor.iniciar_mentoria(self.e, 'Duplicada')
        m = mentor.visualizar_mentorias()[0]
        mentor.editar_comentarios(m.id, 'Editado')
        self.assertEqual(mentor.visualizar_mentorias()[0].comentarios, 'Editado')
        self.s.atuacao(self.b, self.h).sair_hackathon()
        self.s.hackathon(self.h).entrar(self.b, 'mentor')
        with self.assertRaises(ValueError):
            self.s.mentor(self.b, self.h).editar_comentarios(m.id, 'Indevido')
        jurado = self.s.jurado(self.j, self.h)
        with self.assertRaises(ValueError):
            jurado.editar_avaliacao(p, 7, 'Não existe')
        jurado.avaliar_projeto(p, 7, 'Inicial')
        with self.assertRaises(ValueError):
            jurado.avaliar_projeto(p, 8, 'Duplicada')
        jurado.editar_avaliacao(p, 9, 'Editada')
        self.assertEqual(jurado.visualizar_projetos('avaliados')[0]['nota'], 9)

    def test_menus_mentor_jurado_organizador(self):
        p = self.projeto()
        terminal = CLI(self.s)
        with contextlib.redirect_stdout(io.StringIO()):
            with patch('builtins.input', side_effect=[str(self.e), 'Dica pelo menu']):
                terminal.mentor(self.m, self.h, '2')
            m = self.s.mentor(self.m, self.h).visualizar_mentorias()[0]
            with patch('builtins.input', side_effect=[str(m.id), 'Dica editada']):
                terminal.mentor(self.m, self.h, '3')
            with patch('builtins.input', side_effect=[str(p), '8', 'Nota pelo menu']):
                terminal.jurado(self.j, self.h, '4')
            with patch('builtins.input', side_effect=[str(p), '9', 'Nota editada']):
                terminal.jurado(self.j, self.h, '5')
            with patch('builtins.input', side_effect=['1', 'Novo', '2026-10-01', '2026-10-02', '3']):
                terminal.organizador(self.o)
        self.assertEqual(self.s.mentor(self.m, self.h).visualizar_mentorias()[0].comentarios, 'Dica editada')
        self.assertEqual(self.s.jurado(self.j, self.h).visualizar_projetos()[0]['nota'], 9)
        self.assertEqual(len(self.s.hackathons()), 2)


    def test_edicao_sem_historico_nao_pede_id(self):
        cli = CLI(self.s)
        with patch('builtins.input') as entrada, contextlib.redirect_stdout(io.StringIO()):
            cli.mentor(self.m, self.h, '3')
            cli.jurado(self.j, self.h, '5')
        entrada.assert_not_called()

    def test_cancelar_ids_sem_modificacoes(self):
        p = self.projeto()
        mentor = self.s.mentor(self.m, self.h)
        mentor.iniciar_mentoria(self.e, 'Original')
        jurado = self.s.jurado(self.j, self.h)
        jurado.avaliar_projeto(p, 8, 'Original')
        cli = CLI(self.s)
        for acao in (lambda: cli.mentor(self.m, self.h, '2'),
                     lambda: cli.mentor(self.m, self.h, '3'),
                     lambda: cli.jurado(self.j, self.h, '5')):
            with patch('builtins.input', side_effect=['0']) as entrada, contextlib.redirect_stdout(io.StringIO()):
                acao()
            self.assertEqual(entrada.call_count, 1)
        self.assertEqual(mentor.visualizar_mentorias()[0].comentarios, 'Original')
        self.assertEqual(jurado.visualizar_projetos()[0]['nota'], 8)


    def test_ranking_media_empate_e_historico(self):
        p = self.projeto()
        e2 = self.s.participante(self.b, self.h).criar_equipe('Equipe B')
        evento = self.s.hackathon(self.h)
        self.assertTrue(all(r['posicao'] is None for r in evento.ranking()))
        self.s.equipe(e2).salvar_projeto(self.b, 'Outro', 'Descrição', 'Área')
        p2 = self.s.equipe(e2).visualizar_projeto().id
        jurado = self.s.jurado(self.j, self.h)
        jurado.avaliar_projeto(p, 8, 'Bom')
        jurado.avaliar_projeto(p2, 9, 'Ótimo')
        self.s.atuacao(self.m, self.h).sair_hackathon()
        self.s.hackathon(self.h).entrar(self.m, 'jurado')
        self.s.jurado(self.m, self.h).avaliar_projeto(p, 10, 'Ótimo')
        ranking = evento.ranking()
        self.assertEqual([r['media'] for r in ranking], [9, 9])
        self.assertEqual([r['posicao'] for r in ranking], [1, 1])
        self.assertEqual(ranking[0]['avaliacoes'], 2)
        jurado.editar_avaliacao(p2, 10, 'Revisado')
        self.assertEqual(evento.ranking()[0]['equipe_id'], e2)
        jurado.sair_hackathon()
        self.assertEqual(evento.ranking()[0]['media'], 10)
        outro = self.s.organizador(self.o).criar_hackathon('Vazio', '2026-10-01', '2026-10-02', 1)
        self.assertEqual(self.s.hackathon(outro).ranking(), [])
        self.s.equipe(e2).excluir_projeto(self.b)
        self.assertIsNone(evento.ranking()[-1]['posicao'])

    def test_ranking_menus_todos_papeis(self):
        cli = CLI(self.s)
        for u in (self.a, self.m, self.j):
            with patch('builtins.input', side_effect=['6' if u == self.j else '4', '0']), contextlib.redirect_stdout(io.StringIO()) as saida:
                cli.hackathon(u, self.h)
            self.assertIn('RANKING / Evento', saida.getvalue())
            self.assertIn('Equipe A', saida.getvalue())
        with patch('builtins.input', side_effect=['5', str(self.h)]), contextlib.redirect_stdout(io.StringIO()) as saida:
            cli.organizador(self.o)
        self.assertIn('RANKING / Evento', saida.getvalue())
        with patch('builtins.input', side_effect=['5', '0']), contextlib.redirect_stdout(io.StringIO()) as saida:
            cli.organizador(self.o)
        self.assertNotIn('RANKING /', saida.getvalue())


class DatabaseTest(unittest.TestCase):
    def test_transacao_confirma_e_desfaz(self):
        db = Database(':memory:')
        try:
            with db:
                db.execute("INSERT INTO usuarios(nome,email,senha) VALUES('Ana','ana@teste','hash')")
            with self.assertRaises(ValueError):
                with db:
                    db.execute("UPDATE usuarios SET nome='Alterado' WHERE id=1")
                    raise ValueError('Cancelar operação')
            self.assertEqual(db.obter('usuarios', 1)['nome'], 'Ana')
            self.assertIsNone(db.inscricao(1, 999))
            db.criar_tabelas()
            self.assertEqual(db.obter('usuarios', 1)['nome'], 'Ana')
        finally:
            db.close()


class PersistenciaTest(unittest.TestCase):
    def test_main_nao_executa_seed(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / 'teste.db'
            with patch('main.Database', side_effect=lambda: Database(caminho)), patch('builtins.input', return_value='3'), contextlib.redirect_stdout(io.StringIO()) as saida:
                main()
            db = Database(caminho)
            try:
                self.assertEqual(db.execute('SELECT count(*) FROM usuarios').fetchone()[0], 0)
                self.assertEqual(db.execute('SELECT count(*) FROM hackathons').fetchone()[0], 0)
                self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='seeds'").fetchone())
                self.assertNotIn('Senha:', saida.getvalue())
            finally:
                db.close()

    def test_reabrir_banco_e_seed_idempotente(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / 'teste.db'
            db = Database(caminho)
            with contextlib.redirect_stdout(io.StringIO()) as saida:
                preparar(db)
                preparar(db)
            senha = saida.getvalue().split('Senha: ')[1].splitlines()[0]
            self.assertEqual(senha, 'Adm123!')
            self.assertEqual(saida.getvalue().count('Senha: Adm123!'), 2)
            self.assertEqual(saida.getvalue().count('ana@demo.local | Participante'), 1)
            self.assertIn('ana@demo.local | participante', saida.getvalue())
            self.assertIn('Demonstração disponível:', saida.getvalue())
            self.assertEqual(saida.getvalue().count('Demo123!'), 2)
            db.close()
            db = Database(caminho)
            try:
                self.assertEqual(Sistema(db).login('organizador@local', senha), 1)
                self.assertEqual(db.execute('SELECT count(*) FROM usuarios').fetchone()[0], 9)
                self.assertEqual(db.execute('SELECT count(*) FROM hackathons').fetchone()[0], 1)
                self.assertEqual(db.execute('SELECT count(*) FROM equipes').fetchone()[0], 2)
                self.assertEqual(db.execute('SELECT count(*) FROM mentorias').fetchone()[0], 2)
                self.assertEqual(db.execute('SELECT count(*) FROM avaliacoes').fetchone()[0], 3)
            finally:
                db.close()


if __name__ == '__main__':
    unittest.main()

