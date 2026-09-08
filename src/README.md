# Sistema de Hackathons

Implementação local do documento **Hackathon Terminal System.pdf**, em Python e SQLite, exclusivamente pelo terminal.

## Executar

Requer Python 3.10 ou superior. Para preparar o organizador e os dados de exemplo, abra o terminal nesta pasta e execute uma vez:

```console
python seed.py
```

O seed exibe as contas criadas, seus papéis e credenciais. Depois, inicie o sistema:

```console
python main.py
```

Não é necessário instalar pacotes. O arquivo `hackathon.db` é criado automaticamente nesta pasta e preserva os dados entre execuções. `main.py` apenas abre o sistema e inicializa as tabelas: não executa o seed nem cria contas ou eventos automaticamente. Sem executar o seed em um banco novo, o sistema inicia vazio.

Na primeira execução de `python seed.py`, se não houver organizador, ele é cadastrado com o e-mail `organizador@local`. A senha é `Adm123!` e aparece em todas as execuções do seed. Se já existir organizador, sua senha é atualizada para `Adm123!`. O cadastro público cria apenas usuários comuns. O organizador acessa diretamente seu menu de gerenciamento. As senhas são armazenadas com salt individual e PBKDF2-HMAC-SHA256.

## Fluxo de uso

### Dados de demonstração

Somente ao executar `python seed.py`, o seed adiciona uma única vez um hackathon de demonstração com 2 equipes (EcoTech e EduCode), 4 participantes, 2 projetos, 2 mentores, 2 mentorias, 2 jurados e 3 avaliações. Funciona também em um banco criado pela versão anterior, preservando contas e eventos existentes, com atualização da senha dos organizadores para `Adm123!`. Não apague seu `hackathon.db` para atualizar. Se o seed já foi aplicado, o terminal informa isso e não redefine os dados de demonstração.

As contas de exemplo usam a senha `Demo123!`:

Executar `python seed.py` novamente também exibe o organizador, o resumo atual da demonstração, as contas e a senha inicial dos exemplos. A senha do organizador é sempre definida e exibida como `Adm123!`. As senhas dos usuários comuns não são alteradas.

| E-mail | Papel |
| --- | --- |
| ana@demo.local | Participante, líder da EcoTech |
| bruno@demo.local | Participante da EcoTech |
| carla@demo.local | Participante, líder da EduCode |
| diego@demo.local | Participante da EduCode |
| marina@demo.local | Mentor da EcoTech |
| rafael@demo.local | Mentor da EduCode |
| julia@demo.local | Jurado, avaliou os dois projetos |
| pedro@demo.local | Jurado, ainda não avaliou o EduCode |

Se um desses e-mails já existir, o seed usa um sufixo nas novas contas e exibe os e-mails efetivos no terminal. A tabela `seeds` registra a aplicação: executar novamente não duplica os dados nem recria o evento se você o excluir.

Na opção **Entrar em um hackathon**, uma lista vazia retorna ao menu; o ID é validado antes da escolha do papel. Digite `0` no campo de ID para voltar ao menu.

### Uso dos menus

1. Entre como organizador e crie um hackathon com datas no formato `AAAA-MM-DD` e limite positivo de equipes.
2. Faça logout, cadastre um usuário comum e entre no hackathon como participante, mentor ou jurado.
3. Participantes podem criar uma equipe, procurar equipes pelo nome e entrar, ou consultar sua equipe, membros e projeto.
4. O criador é o líder. O menu da equipe permite renomear, remover membros, transferir liderança e criar, editar ou excluir o projeto e a equipe.
5. Mentores podem iniciar mentorias e consultar ou editar seus comentários.
6. Jurados podem consultar todos os projetos, filtrar os que avaliaram ou ainda não avaliaram e criar ou editar suas próprias avaliações.
7. Cada menu de papel oferece **Sair do hackathon**. Voltar ao menu anterior ou fazer logout não remove a inscrição.

As senhas não aparecem enquanto são digitadas em um terminal normal. Entradas incorretas exibem mensagens e retornam ao menu. `Ctrl+C` encerra o programa.

## Regras e decisões

- Um usuário pode se inscrever em vários hackathons, com um único papel em cada um. Para trocar de papel, precisa sair e entrar novamente.
- Cada participante pertence a no máximo uma equipe por hackathon. A criação respeita o limite de equipes, inclusive ao editar o limite do evento.
- O líder deve transferir a liderança antes de sair. Se estiver sozinho, precisa excluir a equipe. Não pode remover a si mesmo pelo menu de membros.
- Cada equipe possui no máximo um projeto. Somente seu líder pode alterá-lo. A edição mantém o ID e as avaliações existentes.
- Há uma mentoria por par mentor/equipe, com comentários editáveis; uma avaliação por par jurado/projeto, também editável.
- A nota aceita inteiros na faixa do SQLite (64 bits). O PDF não define uma escala, por isso não foi imposta uma faixa de 0 a 10.
- Ao sair, a inscrição e a participação em equipe são removidas. Mentorias e avaliações continuam vinculadas à identidade permanente do usuário. Ao retornar ao mesmo papel, o usuário pode consultá-las e editá-las novamente.
- A exclusão explícita de projeto, equipe ou hackathon remove seus dados dependentes, após confirmação no terminal. A preservação histórica exigida no PDF aplica-se à saída de usuários; o documento não define arquivamento de entidades excluídas.
- O texto menciona “três tipos”, mas enumera quatro: foram implementados organizador, participante, mentor e jurado. Organizador é um perfil previamente cadastrado; os outros três são papéis por hackathon.

## Estrutura

- `main.py`: menus e interação com o terminal.
- `database.py`: classe `Database`, conexão, consultas, tabelas e transações SQLite.
- `models.py`: entidades com seus métodos e regras de negócio, incluindo validações de papel e liderança.
- `services.py`: cadastro, autenticação e carregamento dos objetos da sessão.
- `seed.py`: cadastro inicial idempotente do organizador.
- `test_system.py`: testes automatizados com bancos temporários.

A tabela `usuarios` representa a identidade compartilhada; `inscricoes` associa o usuário ao papel em cada hackathon. `membros` representa a participação na equipe. Mentorias e avaliações referenciam o usuário permanente, não a inscrição removível.

## Organização orientada a objetos

As ações são executadas diretamente nas entidades:

- `Organizador`: criar, editar, visualizar e remover hackathons.
- `Hackathon`: receber inscrições e consultar equipes.
- `Participante`: criar equipe, procurar equipes, entrar em equipe e visualizar sua equipe.
- `Equipe`: renomear, consultar membros, remover participante, transferir liderança e gerenciar projeto.
- `Mentor`: iniciar mentoria, consultar mentorias e editar comentários próprios.
- `Jurado`: consultar projetos, avaliar e editar avaliações próprias.

`Participante`, `Mentor` e `Jurado` compartilham a saída do evento por `Usuario`. Cada objeto possui `hackathon_id`; o mesmo usuário pode ter objetos de papéis diferentes em eventos distintos. Cada ação consulta o vínculo atual no banco: guardar um objeto não permite continuar agindo depois de sair ou trocar de papel. A equipe também revalida o líder no banco em cada alteração.

Exemplo, com IDs de um usuário e de um hackathon em que ele já está inscrito como participante:

```python
participante = sistema.participante(usuario_id, hackathon_id)
participante.entrar_equipe(equipe_id)
equipe = participante.visualizar_equipe()
print(equipe.visualizar_participantes())
```

As classes que consultam o banco recebem a conexão SQLite pelo argumento obrigatório `db` no construtor, por exemplo `Participante(id, nome, email, hackathon_id, db=db)`. `Participante`, `Mentor` e `Jurado` herdam esse argumento de `Usuario`. A mesma instância de `Database` é compartilhada pelas classes. Ela oferece `execute`, `executemany`, `obter`, `inscricao`, `criar_tabelas` e `close`. O bloco `with db:` confirma as alterações quando termina normalmente e desfaz a transação em caso de erro, sem fechar a conexão. A validação de papel fica em `models.py`; o banco apenas consulta a inscrição. Erros de validação usam o `ValueError` nativo do Python, tratado pelos menus. Não há dependência dos modelos em `services.py`, nem mudança no esquema do banco: mantenha o `hackathon.db` existente ao atualizar. `main.py` continua separado de `seed.py`.

## Ranking das equipes

Participantes e mentores acessam **4 - Ver ranking das equipes**; jurados acessam **6 - Ver ranking das equipes** no menu do hackathon. Organizadores acessam **5 - Ver ranking das equipes** e selecionam o evento; `0` cancela essa seleção.

O ranking usa a média aritmética de todas as avaliações do projeto, em ordem decrescente. Exibe equipe, projeto, média com duas casas decimais e quantidade de avaliações. Médias iguais compartilham posição (1, 1, 3); o nome ordena a exibição dentro do empate. A classificação considera a média antes do arredondamento. Equipes sem projeto ou sem avaliações aparecem no final, sem classificação. Avaliações históricas de jurados que saíram continuam contando. O ranking é recalculado a cada consulta.

### Executar testes

```console
python -m unittest -v
```

Os testes não alteram o banco real. Para copiar os dados, encerre o sistema e copie `hackathon.db` junto com o projeto. Não compartilhe esse arquivo como código-fonte, pois contém os cadastros e hashes de senha.


Todas as seleções de ID aceitam 0 para voltar ao menu sem alterar dados. Quando a lista está vazia, o sistema retorna sem pedir ID. IDs inválidos podem ser corrigidos na própria seleção. Editar comentários ou avaliações exige um registro próprio já existente.




