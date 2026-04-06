/**
 * onboarding.js — Modal de boas-vindas por nível de usuário
 * Exibe apenas na primeira visita de cada perfil (localStorage).
 * Usa Bootstrap 5 (já carregado nos base templates).
 */

(function () {
  'use strict';

  // ── Conteúdo por perfil ───────────────────────────────────────────────────

  const STEPS = {
    superadmin: [
      {
        icon: 'bi-building-gear',
        cor: '#ff4e17',
        titulo: 'Plataforma FARTECH',
        texto:
          'Você está no painel <strong>SuperAdmin</strong> da FARTECH. '
          + 'Aqui você gerencia todos os tenants (empresas clientes), '
          + 'monitora usuários e acompanha a saúde da plataforma.',
      },
      {
        icon: 'bi-diagram-3',
        cor: '#ff4e17',
        titulo: 'Gestão de Tenants',
        texto:
          'Cada empresa contratante opera em seu próprio <strong>tenant isolado</strong>. '
          + 'Você pode ativar, desativar e monitorar cada tenant '
          + 'pela seção <em>Tenants</em> no menu lateral.',
      },
      {
        icon: 'bi-shield-check',
        cor: '#ff4e17',
        titulo: 'Acesso privilegiado',
        texto:
          'Como SuperAdmin, você enxerga dados de <strong>todas as empresas</strong>. '
          + 'Use esse acesso com responsabilidade. '
          + 'Alterações em tenants são irreversíveis.',
      },
    ],

    administrador: [
      {
        icon: 'bi-speedometer2',
        cor: '#ff4e17',
        titulo: 'Bem-vindo ao POLSEC',
        texto:
          'Você é <strong>Administrador</strong> do sistema patrimonial. '
          + 'O <em>Dashboard</em> exibe uma visão geral dos seus bens: '
          + 'totais por status, distribuição por setor e alertas.',
      },
      {
        icon: 'bi-boxes',
        cor: '#ff4e17',
        titulo: 'Gestão de Patrimônios',
        texto:
          'Em <strong>Patrimônios</strong> você cadastra, edita e controla '
          + 'todos os bens da organização. Use os filtros de categoria e status '
          + 'para localizar rapidamente qualquer item.',
      },
      {
        icon: 'bi-clipboard2-pulse',
        cor: '#ff4e17',
        titulo: 'Chamados & SLA',
        texto:
          'Na seção <strong>Admin → Chamados</strong> você gerencia solicitações '
          + 'de manutenção com controle de SLA por prioridade. '
          + 'Configure prazos em <em>Admin → Configurações de SLA</em>.',
      },
      {
        icon: 'bi-people',
        cor: '#ff4e17',
        titulo: 'Usuários & Funcionários',
        texto:
          'Cadastre <strong>funcionários</strong>, atribua <strong>técnicos</strong> aos chamados '
          + 'e gerencie os <strong>usuários</strong> do sistema em '
          + '<em>Admin → Usuários</em>.',
      },
    ],

    operador: [
      {
        icon: 'bi-clipboard2-pulse',
        cor: '#0078d7',
        titulo: 'Painel do Técnico',
        texto:
          'Você é <strong>Técnico</strong> neste sistema. '
          + 'Seu painel exibe os chamados atribuídos a você '
          + 'com status, prioridade e SLA restante.',
      },
      {
        icon: 'bi-arrow-repeat',
        cor: '#0078d7',
        titulo: 'Atualizando chamados',
        texto:
          'Para cada chamado, você pode <strong>atualizar o status</strong> '
          + '(Em Atendimento, Aguardando Peça, Concluído…) '
          + 'e registrar a <strong>solução aplicada</strong>.',
      },
      {
        icon: 'bi-wifi-off',
        cor: '#0078d7',
        titulo: 'Funciona offline!',
        texto:
          'O app funciona <strong>mesmo sem internet</strong>. '
          + 'Dentro do presídio, suas atualizações ficam salvas localmente '
          + 'e são enviadas automaticamente quando o sinal voltar.',
      },
    ],

    visualizador: [
      {
        icon: 'bi-eye',
        cor: '#6c757d',
        titulo: 'Acesso de Visualização',
        texto:
          'Você possui acesso <strong>somente leitura</strong> ao sistema. '
          + 'Você pode consultar patrimônios, chamados e relatórios, '
          + 'mas não pode realizar alterações.',
      },
      {
        icon: 'bi-boxes',
        cor: '#6c757d',
        titulo: 'O que você pode ver',
        texto:
          'Explore o <strong>Dashboard</strong> com KPIs em tempo real, '
          + 'a lista de <strong>Patrimônios</strong> com filtros, '
          + 'e os <strong>Chamados</strong> abertos na organização.',
      },
    ],
  };

  // ── Helpers ────────────────────────────────────────────────────────────────

  function storageKey(perfil) {
    return 'polsec_onboarding_v1_' + perfil;
  }

  function jaViu(perfil) {
    try {
      return localStorage.getItem(storageKey(perfil)) === '1';
    } catch (_) {
      return true; // se localStorage bloqueado, não exibe
    }
  }

  function marcarVisto(perfil) {
    try {
      localStorage.setItem(storageKey(perfil), '1');
    } catch (_) {}
  }

  // ── Construção do modal ────────────────────────────────────────────────────

  function construirModal(perfil, steps) {
    const totalSteps = steps.length;
    let stepAtual = 0;

    // ── Overlay backdrop
    const backdrop = document.createElement('div');
    backdrop.id = 'onboarding-backdrop';
    backdrop.style.cssText = [
      'position:fixed', 'inset:0', 'z-index:1055',
      'background:rgba(0,0,0,.55)', 'display:flex',
      'align-items:center', 'justify-content:center',
      'padding:1rem',
    ].join(';');

    // ── Card principal
    const card = document.createElement('div');
    card.style.cssText = [
      'background:#fff', 'border-radius:1rem',
      'max-width:480px', 'width:100%',
      'box-shadow:0 20px 60px rgba(0,0,0,.25)',
      'overflow:hidden', 'position:relative',
    ].join(';');

    // ── Progress bar
    const progressWrap = document.createElement('div');
    progressWrap.style.cssText = 'height:4px;background:#e9ecef;';
    const progressBar = document.createElement('div');
    progressBar.style.cssText = 'height:4px;transition:width .35s ease;';
    progressWrap.appendChild(progressBar);

    // ── Body
    const body = document.createElement('div');
    body.style.cssText = 'padding:2rem 2rem 1.5rem;';

    // ── Ícone
    const iconWrap = document.createElement('div');
    iconWrap.style.cssText = [
      'width:64px', 'height:64px', 'border-radius:1rem',
      'display:flex', 'align-items:center', 'justify-content:center',
      'margin-bottom:1.25rem', 'font-size:2rem',
    ].join(';');
    const iconEl = document.createElement('i');
    iconWrap.appendChild(iconEl);

    // ── Título
    const titulo = document.createElement('h5');
    titulo.style.cssText = 'font-weight:700;margin-bottom:.75rem;font-size:1.15rem;';

    // ── Texto
    const texto = document.createElement('p');
    texto.style.cssText = 'color:#6c757d;font-size:.92rem;line-height:1.6;margin-bottom:0;';

    body.appendChild(iconWrap);
    body.appendChild(titulo);
    body.appendChild(texto);

    // ── Footer com navegação
    const footer = document.createElement('div');
    footer.style.cssText = [
      'display:flex', 'justify-content:space-between',
      'align-items:center', 'padding:.75rem 2rem 1.5rem;',
    ].join(';');

    const indicador = document.createElement('span');
    indicador.style.cssText = 'font-size:.78rem;color:#adb5bd;';

    const btnPular = document.createElement('button');
    btnPular.type = 'button';
    btnPular.textContent = 'Pular';
    btnPular.style.cssText = [
      'background:none', 'border:none',
      'font-size:.82rem', 'color:#adb5bd',
      'cursor:pointer', 'padding:.25rem .5rem',
      'text-decoration:underline',
    ].join(';');

    const navDir = document.createElement('div');
    navDir.style.cssText = 'display:flex;gap:.5rem;';

    const btnAnterior = document.createElement('button');
    btnAnterior.type = 'button';
    btnAnterior.textContent = 'Anterior';
    btnAnterior.style.cssText = [
      'padding:.4rem 1rem', 'border-radius:.5rem',
      'border:1px solid #dee2e6', 'background:#fff',
      'font-size:.85rem', 'cursor:pointer', 'display:none',
    ].join(';');

    const btnProximo = document.createElement('button');
    btnProximo.type = 'button';
    btnProximo.style.cssText = [
      'padding:.4rem 1.25rem', 'border-radius:.5rem',
      'border:none', 'color:#fff',
      'font-size:.85rem', 'cursor:pointer',
      'font-weight:600',
    ].join(';');

    navDir.appendChild(btnAnterior);
    navDir.appendChild(btnProximo);
    footer.appendChild(indicador);
    footer.appendChild(btnPular);
    footer.appendChild(navDir);

    card.appendChild(progressWrap);
    card.appendChild(body);
    card.appendChild(footer);
    backdrop.appendChild(card);

    // ── Renderizar step
    function renderStep() {
      const s = steps[stepAtual];
      const cor = s.cor || '#ff4e17';
      const pct = ((stepAtual + 1) / totalSteps) * 100;

      progressBar.style.background = cor;
      progressBar.style.width = pct + '%';

      iconWrap.style.background = cor + '1a'; // 10% opacity hex
      iconEl.className = 'bi ' + s.icon;
      iconEl.style.color = cor;

      titulo.textContent = s.titulo;
      texto.innerHTML = s.texto;

      indicador.textContent = (stepAtual + 1) + ' / ' + totalSteps;

      btnAnterior.style.display = stepAtual > 0 ? 'inline-block' : 'none';

      const ultimo = stepAtual === totalSteps - 1;
      btnProximo.textContent = ultimo ? 'Entendido!' : 'Próximo';
      btnProximo.style.background = cor;
    }

    function fechar() {
      marcarVisto(perfil);
      backdrop.remove();
    }

    btnProximo.addEventListener('click', function () {
      if (stepAtual < totalSteps - 1) {
        stepAtual++;
        renderStep();
      } else {
        fechar();
      }
    });

    btnAnterior.addEventListener('click', function () {
      if (stepAtual > 0) {
        stepAtual--;
        renderStep();
      }
    });

    btnPular.addEventListener('click', fechar);

    // Fechar ao clicar no backdrop (fora do card)
    backdrop.addEventListener('click', function (e) {
      if (e.target === backdrop) fechar();
    });

    renderStep();
    return backdrop;
  }

  // ── Inicialização ──────────────────────────────────────────────────────────

  function init() {
    const perfil = document.body.dataset.perfil;
    if (!perfil) return;

    const steps = STEPS[perfil];
    if (!steps) return;

    if (jaViu(perfil)) return;

    const modal = construirModal(perfil, steps);
    document.body.appendChild(modal);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
